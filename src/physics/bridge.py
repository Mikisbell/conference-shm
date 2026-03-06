"""
src/physics/bridge.py — Sincronizador Belico
=============================================
Lazo cerrado entre Arduino (físico) y OpenSeesPy (digital).

Protocolo:
  0. Handshake SSOT: verifica que Arduino y bridge usan el mismo config hash.
  1. Timestamping dual: millis() de Arduino vs time.time_ns() de Linux.
  2. Buffer con suavizado: mantiene buffer_depth paquetes para absorber jitter.
  3. Inyección en OpenSeesPy: solo paquetes válidos disparan ops.analyze(1, dt).
  4. Watchdog: jitter promedio > max_jitter_ms → pipeline suspendido.
  5. Modo predicción: aceleración > trigger_g → worst-case en paralelo.
  6. Protocolo de Aborto (RED LINES):
       RL-1: 3 paquetes CONSECUTIVOS con jitter > 10ms
       RL-2: σ_sensor > 0.85·fy
       RL-3: OpenSeesPy no converge en < 10 iteraciones

Dependencias: openseespy, pyserial, pyyaml, numpy
Uso: python -m src.physics.bridge [/dev/ttyUSB0]
"""

import time
import hashlib
import statistics
import threading
import inspect
from collections import deque
from pathlib import Path

import yaml
import serial
import numpy as np
import openseespy.opensees as ops
import sys

# Resolver rutas centralizadas
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from config.paths import get_params_file, get_processed_data_dir

from src.physics.kalman import RealTimeKalmanFilter1D
from src.physics.engram_client import EngramClient

# ─────────────────────────────────────────────────────────
# CARGA DE CONFIGURACIÓN SSOT
# ─────────────────────────────────────────────────────────
PARAMS_PATH = get_params_file()

def load_config() -> dict:
    with open(PARAMS_PATH, "r") as f:
        return yaml.safe_load(f)

def compute_config_hash(path: Path) -> str:
    """SHA-256 del archivo params.yaml — fuente única de verdad."""
    sha = hashlib.sha256()
    sha.update(path.read_bytes())
    return sha.hexdigest()


# ─────────────────────────────────────────────────────────
# PASO 0: HANDSHAKE SSOT
# ─────────────────────────────────────────────────────────
def handshake(ser: serial.Serial, cfg: dict, config_hash: str) -> bool:
    """
    Envía el token de handshake y el hash de configuración al Arduino.
    Espera confirmación. Si no coincide, aborta.
    """
    token = cfg["temporal"]["handshake_token"]["value"]
    message = f"HANDSHAKE:{token}:{config_hash[:8]}\n"
    ser.write(message.encode())
    response = ser.readline().decode().strip()

    if response.startswith("ACK"):
        print(f"[BRIDGE] ✅ Handshake exitoso: {response}")
        return True
    else:
        print(f"[BRIDGE] ❌ Handshake fallido. Arduino respondió: '{response}'")
        print("[BRIDGE]    Verifica que src/firmware/params.h fue generado desde el mismo params.yaml.")
        return False


# ─────────────────────────────────────────────────────────
# PARSER DE PAQUETES DEL SENSOR
# ─────────────────────────────────────────────────────────
def parse_packet(raw: str) -> dict | None:
    """
    Formato Clásico (100Hz):
      T:<millis>,A:<accel_g>,D:<disp_mm>
    Formato LoRa Edge AI (Asíncrono):
      LORA:T:<unix_s>,TMP:<temp>,HUM:<hum>,FN:<fn>,MAX_G:<max_g>,STAT:<stat>
    """
    try:
        # ─ PAQUETE LORA EDGE AI ─
        if raw.startswith("LORA:"):
            # LORA:T:1760000000,TMP:28.1,HUM:55.2,FN:5.20,MAX_G:1.15,STAT:OK
            body = raw[5:] # Remover prefijo LORA:
            parts = dict(p.split(":") for p in body.strip().split(","))
            return {
                "is_lora": True,
                "t_unix": int(parts.get("T", 0)),
                "tmp": float(parts.get("TMP", 25.0)),
                "hum": float(parts.get("HUM", 0.0)),
                "fn": float(parts.get("FN", 0.0)),
                "max_g": float(parts.get("MAX_G", 0.0)),
                "stat": parts.get("STAT", "ERR"),
                "vbat": float(parts.get("BAT", 4.0)),   # V (4.0 = sin dato = asumir sano)
                "rssi": int(parts.get("RSSI", -80)),    # dBm (E32 a veces lo incluye)
            }

        # ─ PAQUETE RAW CLÁSICO ─
        parts = dict(p.split(":") for p in raw.strip().split(","))
        return {
            "is_lora": False,
            "t_arduino_ms": int(parts["T"]),
            "accel_g":      float(parts["A"]),
            "disp_mm":      float(parts.get("D", 0.0)),
        }
    except (ValueError, KeyError):
        return None


# ─────────────────────────────────────────────────────────
# CÁLCULO DE JITTER (Clock Drift)
# ─────────────────────────────────────────────────────────
def compute_jitter_ms(t_arduino_ms: int, t_linux_ns: int, baseline_offset_ms: float) -> float:
    """
    Compara el reloj del Arduino (millis) con el reloj de Linux (time.time_ns).
    Devuelve la desviación respecto al offset de referencia medido en el handshake.
    """
    t_linux_ms = t_linux_ns / 1_000_000
    drift = abs((t_linux_ms - t_arduino_ms) - baseline_offset_ms)
    return drift


# ─────────────────────────────────────────────────────────
# INYECCIÓN EN OPENSEESPY (Cámara de Tortura)
# ─────────────────────────────────────────────────────────
def inject_and_analyze(accel_g: float, dt: float, model_props: dict = None) -> dict:
    """
    Apply sensor acceleration to OpenSeesPy model and advance one step.
    model_props comes from torture_chamber.init_model() return value.

    Adapts to both linear (1 element, node 2) and nonlinear (multi-element,
    top_node from model_props) configurations automatically.
    """
    if model_props is None:
        model_props = {}

    mass_kg = model_props.get("mass_kg", 1000.0)
    I_m4 = model_props.get("I_m4", 0.25**4 / 12.0)
    b_m = model_props.get("b_m", 0.25)
    c = b_m / 2.0  # distance to neutral axis
    top_node = model_props.get("top_node", 2)

    force = mass_kg * accel_g * 9.81  # N

    ops.load(top_node, force, 0.0, 0.0)
    ok = ops.analyze(1, dt)

    try:
        ops.reactions()
        Mz_base = abs(ops.nodeReaction(1, 3))
        # For linear model: elastic beam theory sigma = Mc/I
        # For nonlinear model: this is an approximation — fiber section
        # tracks actual stress internally, but Mc/I gives a comparable metric
        stress_pa = (Mz_base * c) / I_m4
    except Exception:
        stress_pa = 0.0

    return {
        "converged": ok == 0,
        "stress_pa": stress_pa,
    }


# ─────────────────────────────────────────────────────────
# MODO PREDICCION (Placeholder — requiere implementacion)
# ─────────────────────────────────────────────────────────
def run_worst_case_prediction(accel_g: float, cfg: dict):
    """
    Placeholder for worst-case prediction mode.
    TODO: Implement when PgNN surrogate is integrated into real-time loop.
    Currently logs the trigger event only.
    """
    threshold = cfg["temporal"]["prediction_mode"]["trigger_threshold_g"]["value"]
    if accel_g > threshold:
        print(f"[BRIDGE] PREDICTION MODE TRIGGERED — accel={accel_g:.3f}g > {threshold}g (not yet implemented)")


# ─────────────────────────────────────────────────────────
# WATCHDOG — Monitor de Integridad Temporal
# ─────────────────────────────────────────────────────────
class JitterWatchdog:
    def __init__(self, max_jitter_ms: float, warning_ms: float):
        self.max_jitter_ms = max_jitter_ms
        self.warning_ms    = warning_ms
        self.history: deque = deque(maxlen=50)  # ventana deslizante de 50 paquetes

    def record(self, jitter_ms: float) -> str:
        """Registra un valor de jitter y devuelve el estado: OK | WARNING | BLOCKED."""
        self.history.append(jitter_ms)
        avg = statistics.mean(self.history)

        if avg > self.max_jitter_ms:
            return "BLOCKED"
        elif avg > self.warning_ms:
            return "WARNING"
        return "OK"

    def average(self) -> float:
        return statistics.mean(self.history) if self.history else 0.0


# ─────────────────────────────────────────────────────────
# PROTOCOLO DE ABORTO — Las 3 Red Lines
# ─────────────────────────────────────────────────────────
class AbortController:
    """
    Monitor de las 3 condiciones de línea roja del Protocolo de Aborto.
    Si cualquiera se activa, emit_shutdown=True y el caller envía SHUTDOWN al Arduino.

    RL-1: Jitter consecutivo  — 3 paquetes SEGUIDOS con jitter > abort_jitter_ms
    RL-2: Esfuerzo crítico    — σ_sensor > 0.85 · fy
    RL-3: Divergencia numérica — OpenSeesPy no converge en el paso actual
    """
    ABORT_JITTER_MS     = 10.0  # ms   (RL-1, fijo por Protocolo Bélico)
    JITTER_CONSEC_LIMIT = 3     # paquetes seguidos (RL-1)
    STRESS_RATIO_ABORT  = 0.85  # fracción de fy (RL-2)

    def __init__(self, fy_pa: float):
        self.fy_pa          = fy_pa
        self.jitter_consec  = 0      # contador de paquetes consecutivos
        self.abort_reason   = None

    def check_rl1_jitter(self, jitter_ms: float) -> bool:
        """RL-1: 3 paquetes consecutivos con jitter > 10ms."""
        if jitter_ms > self.ABORT_JITTER_MS:
            self.jitter_consec += 1
            if self.jitter_consec >= self.JITTER_CONSEC_LIMIT:
                self.abort_reason = (
                    f"RL-1 JITTER: {self.jitter_consec} paquetes consecutivos "
                    f"con jitter={jitter_ms:.1f}ms > {self.ABORT_JITTER_MS}ms"
                )
                return True
        else:
            self.jitter_consec = 0  # reset si el paquete es bueno
        return False

    def check_rl2_stress(self, stress_pa: float) -> bool:
        """RL-2: σ_sensor > 0.85·fy."""
        limit = self.STRESS_RATIO_ABORT * self.fy_pa
        if stress_pa > limit:
            self.abort_reason = (
                f"RL-2 ESFUERZO: σ={stress_pa/1e6:.2f}MPa > "
                f"0.85·fy={limit/1e6:.2f}MPa"
            )
            return True
        return False

    def check_rl3_convergence(self, converged: bool) -> bool:
        """RL-3: Fallo de convergencia de OpenSeesPy."""
        if not converged:
            self.abort_reason = "RL-3 DIVERGENCIA: OpenSeesPy no convergió en el paso actual."
            return True
        return False

    def triggered(self) -> bool:
        return self.abort_reason is not None


# ─────────────────────────────────────────────────────────
# GUARDIAN ANGEL — Validador de Leyes Físicas Inmutables
# ─────────────────────────────────────────────────────────
class GuardianAngel:
    """
    Protocolo de Integridad Física: rechaza telemetría que viola leyes
    termodinámicas o estructurales fundamentales.

    REGLA S-1 (Rigidez Estructural):
      Un módulo de concreto *reciclado no intervenido* no puede ganar
      rigidez (fn creciente) entre lectura y lectura.
      Tolerancia = +1 Hz (vibración ambiental / ruido de red).

    REGLA S-2 (Temperatura Física):
      La temperatura de un módulo de concreto en climas normales no
      puede superar los 80 °C ni bajar de -5 °C.
      Si llega un 500 °C, ese sensor está alucinando o fue saboteado.

    REGLA S-3 (Gradiente Térmico):
      Un cambio de temperatura mayor a 20 °C entre dos lecturas
      separadas por el intervalo LoRa (5 s) viola la conservación de
      la energía sin fuente externa declarada.
    """
    RIGIDEZ_TOLERANCE_HZ  = 1.0
    RIGIDEZ_EXTREME_HZ    = 3.0
    TEMP_MIN_C            = -5.0
    TEMP_MAX_C            = 80.0
    TEMP_EXTREME_MIN_C    = -15.0
    TEMP_EXTREME_MAX_C    = 120.0
    GRAD_EXTREME_C        = 20.0
    GRAD_IMPOSSIBLE_C     = 50.0
    BAT_UNRELIABLE_V      = 3.5   # V: por debajo el ADC pierde precisión
    BAT_CRITICAL_V        = 3.3   # V: por debajo el oscilador puede desregularse

    def __init__(self):
        self.fn_baseline: float | None = None
        self.tmp_last:    float | None = None
        self.violations:  list[str]    = []

    def validate(self, fn: float, tmp: float, vbat: float = 4.0) -> tuple[str, str | None]:
        """
        Retorna (status, mensaje):
          'ok'         → Paquete válido. Pasa al pipeline.
          'extreme'    → Evento físico real pero anómalo. Auditar, NO bloquear.
          'impossible' → Dato físicamente imposible. Bloquear y sellar en Engram.
        """
        # S-4: Calidad de energía del sensor
        if vbat < self.BAT_CRITICAL_V:
            msg = (f"GUARDIAN_ANGEL [S-4] BATERIA CRITICA: {vbat:.2f}V < {self.BAT_CRITICAL_V}V. "
                   f"Oscilador potencialmente desregulado. Dato BLOQUEADO.")
            self.violations.append(msg)
            return 'impossible', msg
        elif vbat < self.BAT_UNRELIABLE_V:
            msg = (f"GUARDIAN_ANGEL [S-4] BATERIA BAJA: {vbat:.2f}V < {self.BAT_UNRELIABLE_V}V. "
                   f"ADC con precisión reducida. Reemplazar batería en próxima visita.")
            return 'extreme', msg
        # S-1: Rigidez
        if self.fn_baseline is not None:
            delta_fn = fn - self.fn_baseline
            if delta_fn > self.RIGIDEZ_EXTREME_HZ:
                msg = (f"GUARDIAN_ANGEL [S-1] FISICA IMPOSIBLE: fn={fn:.2f}Hz "
                       f"supera baseline={self.fn_baseline:.2f}Hz en +{delta_fn:.2f}Hz "
                       f"(concreto no puede ganar rigidez sin intervención).")
                self.violations.append(msg)
                return 'impossible', msg
            elif delta_fn > self.RIGIDEZ_TOLERANCE_HZ:
                msg = (f"GUARDIAN_ANGEL [S-1] EVENTO EXTREMO: fn={fn:.2f}Hz supó baseline "
                       f"en +{delta_fn:.2f}Hz. Posible impacto directo o refuerzo no declarado.")
                return 'extreme', msg
        else:
            self.fn_baseline = fn

        # S-2: Temperatura
        if not (self.TEMP_EXTREME_MIN_C <= tmp <= self.TEMP_EXTREME_MAX_C):
            msg = (f"GUARDIAN_ANGEL [S-2] FISICA IMPOSIBLE: tmp={tmp:.1f}°C "
                   f"fuera del rango extremo [{self.TEMP_EXTREME_MIN_C},{self.TEMP_EXTREME_MAX_C}]°C.")
            self.violations.append(msg)
            return 'impossible', msg
        elif not (self.TEMP_MIN_C <= tmp <= self.TEMP_MAX_C):
            msg = (f"GUARDIAN_ANGEL [S-2] EVENTO EXTREMO: tmp={tmp:.1f}°C fuera del "
                   f"rango nominal [{self.TEMP_MIN_C},{self.TEMP_MAX_C}]°C. "
                   f"Posible incendio periférico o helada intensa.")
            return 'extreme', msg

        # S-3: Gradiente térmico
        if self.tmp_last is not None:
            grad = abs(tmp - self.tmp_last)
            if grad > self.GRAD_IMPOSSIBLE_C:
                msg = (f"GUARDIAN_ANGEL [S-3] FISICA IMPOSIBLE: ΔT={grad:.1f}°C "
                       f"entre paquetes (máx físico={self.GRAD_IMPOSSIBLE_C}°C).")
                self.violations.append(msg)
                return 'impossible', msg
            elif grad > self.GRAD_EXTREME_C:
                msg = (f"GUARDIAN_ANGEL [S-3] EVENTO EXTREMO: ΔT={grad:.1f}°C. "
                       f"Cambio brusco pero posible en evento climático extremo (El Niño).")
                return 'extreme', msg

        self.tmp_last = tmp
        return 'ok', None


# ─────────────────────────────────────────────────────────
# LOOP PRINCIPAL
# ─────────────────────────────────────────────────────────
def run_bridge(port: str = "/dev/ttyUSB0", reset_baseline: bool = False):
    cfg = load_config()
    config_hash = compute_config_hash(PARAMS_PATH)

    dt           = cfg["temporal"]["dt_simulation"]["value"]
    max_jitter   = cfg["temporal"]["max_jitter_ms"]["value"]
    warn_jitter  = cfg["temporal"]["clock_drift_warning_ms"]["value"]
    buffer_depth = cfg["temporal"]["buffer_depth"]["value"]
    baud         = int(cfg["acquisition"]["serial_baud"]["value"])
    pred_enabled = bool(cfg["temporal"]["prediction_mode"]["enabled"])
    fy_pa        = float(cfg["material"]["yield_strength_fy"]["value"])
    
    # ─ Parámetros Módulo Shadow Play (Kalman)
    kf_enabled   = bool(cfg["signal_processing"]["kalman"]["enabled"])
    kf_q         = float(cfg["signal_processing"]["kalman"]["process_noise_q"]["value"])
    kf_r         = float(cfg["signal_processing"]["kalman"]["measurement_noise_r"]["value"])

    watchdog  = JitterWatchdog(max_jitter, warn_jitter)
    aborter   = AbortController(fy_pa)
    guardian  = GuardianAngel()
    kf        = RealTimeKalmanFilter1D(q=kf_q, r=kf_r) if kf_enabled else None
    buffer: deque = deque(maxlen=buffer_depth)

    print(f"[BRIDGE] 🚀 Iniciando Sincronizador Bélico")
    print(f"[BRIDGE]    Config hash: {config_hash[:16]}...")
    print(f"[BRIDGE]    Puerto: {port} @ {baud} baud")
    print(f"[BRIDGE]    dt={dt}s | max_jitter={max_jitter}ms | buffer={buffer_depth}")
    print(f"[BRIDGE]    fy={fy_pa/1e6:.0f}MPa | RL-2 umbral={0.85*fy_pa/1e6:.0f}MPa")
    print(f"[BRIDGE]    Filtro de Kalman: {'ACTIVADO' if kf_enabled else 'DESACTIVADO'} (Q={kf_q}, R={kf_r})")

    # Fix #3 y #5: cargar o reiniciar calibración de campo
    baseline_yaml = Path("config/field_baseline.yaml")
    
    if reset_baseline:
        if baseline_yaml.exists():
            baseline_yaml.unlink()  # Forzar borrado del archivo
        print(f"[BRIDGE] ♻️  RESET SOLICITADO. field_baseline.yaml eliminado.")
        print(f"[BRIDGE] ⚠️  Guardian Angel usará el primer paquete sano como nuevo baseline post-mantenimiento.")
        # Opcional: registrar en Engram el evento de reset
        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
        EngramClient.record(
            hash_code=current_script_hash,
            payload={"reason": "MAINTENANCE_BASELINE_RESET"},
            tags=["admin", "reset", "baseline"]
        )
    elif baseline_yaml.exists():
        import yaml as _yaml
        with open(baseline_yaml) as _f:
            bl = _yaml.safe_load(_f)
        guardian.fn_baseline = float(bl.get("fn_baseline_hz", 8.0))
        print(f"[BRIDGE] 📍 Baseline de campo cargado: fn_baseline={guardian.fn_baseline} Hz (site: {bl.get('site','?')})")
    else:
        print(f"[BRIDGE] ⚠️  Sin field_baseline.yaml — Guardian Angel usará primer paquete sano como baseline.")

    history_t = []
    history_a = []
    history_s = []
    history_inn = [] # Métrica SHM: Historial de Innovación
    start_time_ns = time.time_ns()

    def send_shutdown(ser: serial.Serial, reason: str):
        """Envía la señal SHUTDOWN al Arduino y registra el motivo."""
        try:
            ser.write(b"SHUTDOWN\n")
        except Exception as e:
            print(f"[BRIDGE] Nota: No se pudo enviar SHUTDOWN al puerto físico (posible desconexión): {e}")
        print(f"\n[BRIDGE] 🛑 SHUTDOWN ENVIADO AL ARDUINO")
        print(f"[BRIDGE]    Motivo: {reason}")
        
        # Guardar en Engram de forma inmutable
        import inspect
        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
        EngramClient.record(
            hash_code=current_script_hash,
            payload={"reason": reason, "packets_processed": len(history_t)},
            tags=["resonance_test", "abort", "shutdown"]
        )
        print(f"\n[BRIDGE] 🛑 SHUTDOWN COMPLETO. Cerrando puente.")
        
        # ─ Volcar snapshot de historia para análisis cívico ─
        import pandas as pd
        proc_dir = get_processed_data_dir()
        
        inn_list = history_inn if len(history_inn) == len(history_a) else [0.0]*len(history_a)
        
        df = pd.DataFrame({
            "time_s": history_t,
            "accel_g": history_a,
            "stress_mpa": [s / 1e6 for s in history_s],
            "innovation_g": inn_list
        })
        
        csv_file = proc_dir / "latest_abort.csv"
        df.to_csv(csv_file, index=False)
        print(f"[BRIDGE]    Snapshot guardado en {csv_file} ({len(df)} muestras)")

    with serial.Serial(port, baud, timeout=2) as ser:
        time.sleep(2)

        # Initialize solver backend based on domain in SSOT
        from src.physics.solver_backend import get_solver_backend
        domain = cfg.get("project", {}).get("domain", "structural")
        print(f"[BRIDGE] Initializing solver backend (domain={domain})...")
        solver_backend = get_solver_backend(cfg)
        model_props = solver_backend.init_model(cfg)

        if not handshake(ser, cfg, config_hash):
            print("[BRIDGE] ❌ PIPELINE BLOQUEADO — Handshake fallido.")
            return

        ser.write(b"TIME_SYNC\n")
        raw = ser.readline().decode().strip()
        pkt = parse_packet(raw)
        baseline_offset_ms = (time.time_ns() / 1_000_000) - pkt["t_arduino_ms"] if pkt else 0.0
        print(f"[BRIDGE]    Offset de reloj base: {baseline_offset_ms:.2f}ms")

        packet_count = 0
        print("[BRIDGE] ✅ Lazo cerrado activo. Ctrl+C para detener.\n")

        try:
            while True:
                t_linux_ns = time.time_ns()
                
                try:
                    raw = ser.readline().decode().strip()
                    if not raw:
                        print("\n[BRIDGE] ⚠️ ALERTA: Tiempo de espera (Timeout) alcanzado.")
                        send_shutdown(ser, "Fallo de Hardware Crítico: Pérdida de Comunicación (Señal Inexistente)")
                        break
                except Exception as e:
                    # Captura OSError / SerialException (Cable Arrancado / Emulador Muerto)
                    print(f"\n[BRIDGE] ⚠️ ERROR CRÍTICO DE ENLACE FÍSICO: {e}")
                    send_shutdown(ser, "DESASTRE DE DATOS: Enlace Serial destruido (Cable desconectado/Sensor apagado)")
                    break

                pkt = parse_packet(raw)
                if pkt is None:
                    print(f"[BRIDGE] ⚠️  Paquete inválido descartado: '{raw}'")
                    continue

                # ─ FLUJO LORA EDGE AI (ASÍNCRONO / EVENTOS) ─
                if pkt.get("is_lora"):
                    latency_s = time.time() - pkt["t_unix"]
                    is_stale  = latency_s > 15.0 # Max 15 segundos admitidos en telemetría
                    
                    status_col = "✅" if pkt["stat"] == "OK" else ("⚠️ " if pkt["stat"] == "WARN" else "🛑")
                    
                    if is_stale:
                        print(f"[LORA Rx] 📡 WATCHDOG TELEMÉTRICO: Abortando paquete. Lag {latency_s:.1f}s > 15s (STALE DATA)")
                        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
                        EngramClient.record(
                            hash_code=current_script_hash,
                            payload={"reason": "LORA_WATCHDOG_STALE", "lag_s": latency_s, "f_n": pkt["fn"], "stat": pkt["stat"]},
                            tags=["lora_telemetry", "error", "stale_data"]
                        )
                        continue

                    # ─ GUARDIAN ANGEL: Validación de Física Inmutable ─
                    ga_status, ga_msg = guardian.validate(
                        fn=pkt["fn"], tmp=pkt["tmp"], vbat=pkt.get("vbat", 4.0)
                    )
                    
                    if ga_status == 'impossible':
                        print(f"\n[BRIDGE] 🚨 GUARDIAN ANGEL: Paquete BLOQUEADO — {ga_msg}")
                        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
                        EngramClient.record(
                            hash_code=current_script_hash,
                            payload={"reason": "GUARDIAN_ANGEL_IMPOSSIBLE", "detail": ga_msg,
                                     "f_n": pkt["fn"], "tmp": pkt["tmp"], "stat": pkt["stat"]},
                            tags=["lora_telemetry", "error", "physics_violation", "guardian_angel", "sabotage"]
                        )
                        print(f"[BRIDGE] 📝 Violación sellada en Engram. BIM NO será actualizado.")
                        continue  # Bloquear contaminación de Engram y BIM
                    
                    elif ga_status == 'extreme':
                        print(f"\n[BRIDGE] ⚠️  GUARDIAN ANGEL: Evento Extremo detectado — {ga_msg}")
                        print(f"[BRIDGE]    Pipeline continúa. Requiere revisión humana.")
                        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
                        EngramClient.record(
                            hash_code=current_script_hash,
                            payload={"reason": "GUARDIAN_ANGEL_EXTREME_EVENT", "detail": ga_msg,
                                     "f_n": pkt["fn"], "tmp": pkt["tmp"], "stat": pkt["stat"]},
                            tags=["lora_telemetry", "warning", "extreme_event", "guardian_angel"]
                        )
                        # → El paquete pasa al rest del pipeline con bandera visible
                        
                    print(f"[LORA Rx] {status_col} Fn: {pkt['fn']:.2f} Hz | Max_G: {pkt['max_g']:.3f} | Latencia: {latency_s:.1f}s | Estado: {pkt['stat']}")
                    packet_count += 1
                    
                    if packet_count == 1 and not pkt["stat"].startswith("ALARM"):
                        print(f"[BRIDGE] 📝 Línea Base (BASELINE) registrada en Engram.")
                        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
                        EngramClient.record(
                            hash_code=current_script_hash,
                            payload={"reason": "BASELINE", "f_n": pkt["fn"], "max_g": pkt["max_g"], "tmp": pkt["tmp"], "lag_s": latency_s},
                            tags=["lora_telemetry", "baseline", pkt["stat"].lower()]
                        )
                        
                    if pkt["stat"].startswith("ALARM"):
                        print(f"\n[BRIDGE] 🛑 ALERTA ESTRUCTURAL LORA: {pkt['stat']} detectada en sensor Edge.")
                        current_script_hash = compute_config_hash(Path(inspect.getfile(inspect.currentframe())))
                        EngramClient.record(
                            hash_code=current_script_hash,
                            payload={"reason": pkt["stat"], "f_n": pkt["fn"], "max_g": pkt["max_g"], "tmp": pkt["tmp"], "lag_s": latency_s},
                            tags=["lora_telemetry", "alarm", pkt["stat"].lower()]
                        )
                        print(f"[BRIDGE] 📝 Evento crítico reportado a Engram para evaluación del Scientific Narrator.")
                        break # Terminar bucle para iniciar reporte automático
                    continue # LoRa no entra al loop de OpenSeesPy a 100Hz

                # ─ FLUJO CLÁSICO USB RAW (SÍNCRONO A 100HZ) ─
                # Calcular jitter
                jitter = compute_jitter_ms(pkt["t_arduino_ms"], t_linux_ns, baseline_offset_ms)
                watch_status = watchdog.record(jitter)

                # RED LINE 1 — Jitter consecutivo
                if aborter.check_rl1_jitter(jitter):
                    send_shutdown(ser, aborter.abort_reason)
                    break

                if watch_status == "BLOCKED":
                    print(f"[BRIDGE] ❌ WATCHDOG — Jitter promedio: {watchdog.average():.2f}ms")
                    send_shutdown(ser, f"Jitter promedio {watchdog.average():.1f}ms > {max_jitter}ms")
                    break
                elif watch_status == "WARNING":
                    print(f"[BRIDGE] ⚡ Jitter warning: {jitter:.2f}ms (avg {watchdog.average():.2f}ms)")

                # ─ Shadow Play - Procesamiento de señal y Monitor SHM
                import math
                inn, s_var = 0.0, 0.0
                if kf_enabled:
                    accel_processed, inn, s_var = kf.step(pkt["accel_g"])
                    
                    # Alerta Temprana SHM: ¿Ruido o Daño Estructural? (z > 2sigma aprox)
                    if abs(inn) > 2.0 * math.sqrt(s_var) and packet_count > 10:
                        print(f"[BRIDGE] ⚠️  SHM EARLY WARNING: Filtración de Innovación detecta posible daño subyacente (Inn={inn:.3g})")
                        
                else:
                    buffer.append(pkt["accel_g"])
                    accel_processed = float(np.mean(buffer))

                # ─ Modo predicción
                if pred_enabled:
                    run_worst_case_prediction(accel_processed, cfg)

                # Inject into solver backend (domain-agnostic)
                result = solver_backend.step(accel_processed, dt, model_props)

                # RED LINE 3 — Divergencia numérica
                if aborter.check_rl3_convergence(result["converged"]):
                    send_shutdown(ser, aborter.abort_reason)
                    break

                # RED LINE 2 — Esfuerzo crítico
                if aborter.check_rl2_stress(result["stress_pa"]):
                    send_shutdown(ser, aborter.abort_reason)
                    break

                # ─ Guardar historial
                elapsed_s = (t_linux_ns - start_time_ns) / 1e9
                history_t.append(elapsed_s)
                history_a.append(accel_processed)
                history_s.append(result["stress_pa"])
                history_inn.append(inn)

                packet_count += 1
                if packet_count % 100 == 0:
                    sigma_mpa = result["stress_pa"] / 1e6
                    print(f"[BRIDGE] 📡 pkts:{packet_count} | jitter:{watchdog.average():.1f}ms | "
                          f"accel:{accel_processed:.4f}g | SHM Inn:{inn:.4f} | σ:{sigma_mpa:.2f}MPa")

        except KeyboardInterrupt:
            print(f"\n[BRIDGE] 🛑 Lazo cerrado detenido.")
            print(f"[BRIDGE]    Total paquetes: {packet_count} | Jitter avg: {watchdog.average():.2f}ms")
            if watchdog.average() > max_jitter:
                print(f"[BRIDGE] ⚠️  ADVERTENCIA VERIFIER: Jitter promedio excedió {max_jitter}ms.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Belico Stack - Bridge")
    parser.add_argument("port", nargs="?", default="/dev/ttyUSB0", help="Puerto serial (ej. /dev/ttyUSB0)")
    parser.add_argument("--reset-baseline", action="store_true", help="Eliminar calibración previa y fijar nuevo baseline post-mantenimiento")
    args = parser.parse_args()
    
    run_bridge(args.port, reset_baseline=args.reset_baseline)
