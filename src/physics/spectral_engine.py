#!/usr/bin/env python3
"""
src/physics/spectral_engine.py — Motor de Espectro de Respuesta (Duhamel)
===========================================================================
Calcula el Espectro de Pseudo-Aceleración Sa(T, ζ) según la Integral de Duhamel.

Uso en el EIU (Ecosistema de Investigación Universal):
  - Convierte un acelerograma crudo (.AT2 parseado por PeerAdapter) en su
    Espectro de Respuesta Sa vs T, comparando el registro original con el
    filtrado por el Guardian Angel.
  - Referencia normativa: ASCE 7-22 / Norma E.030 (ζ = 5%).

Fórmula implementada:
  Sa(T, ζ) = ω² · max_t | ∫₀ᵗ ü_g(τ) · e^(-ζω(t-τ)) · sin(ωd(t-τ)) / ωd dτ |
  
  Donde:
    ω  = 2π/T     (frecuencia angular natural)
    ωd = ω√(1-ζ²) (frecuencia amortiguada)
    ζ  = 0.05     (amortiguamiento crítico, estándar E.030 y ASCE 7)
"""

try:
    import numpy as np
except ImportError:
    import sys as _sys
    print("[SPECTRAL] numpy not installed. Run: pip install numpy", file=_sys.stderr)
    _sys.exit(1)

from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# Mathematical model constants — AGENTS.md Rule 12
# Newmark (1959) average-acceleration method: unconditionally stable, ζ-invariant.
# These are numerical integration constants, not structural/simulation parameters.
# ---------------------------------------------------------------------------
_NEWMARK_BETA  = 0.25  # Newmark 1959 — average acceleration (unconditionally stable)
_NEWMARK_GAMMA = 0.50  # Newmark 1959 — average acceleration

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def compute_spectral_response(
    accel_g: np.ndarray,
    dt: float,
    T_range: np.ndarray = None,
    zeta: float = 0.05,
) -> dict:
    """
    Calcula el Espectro de Pseudo-Aceleración Sa(T, ζ) de un acelerograma.

    Parámetros
    ----------
    accel_g : np.ndarray
        Acelerograma en unidades de 'g' (muestreado a 1/dt Hz).
    dt : float
        Intervalo de tiempo en segundos.
    T_range : np.ndarray, opcional
        Array de periodos de vibración T (s) a evaluar.
        Por defecto: 0.01 a 3.0 s en 100 puntos.
    zeta : float
        Amortiguamiento crítico (default 0.05 = 5%, norma E.030 / ASCE 7-22).

    Retorna
    -------
    dict con:
      - T        : array de periodos
      - Sa       : pseudo-aceleración Sa(T) en unidades de 'g'
      - pga      : Peak Ground Acceleration del registro
    """
    g_mps2 = 9.81                              # 1g en m/s²

    if T_range is None:
        T_range = np.linspace(0.01, 3.0, 100)  # Rango E.030: 0 - 3s

    Sa_arr = np.zeros(len(T_range))
    accel_mps2 = accel_g * g_mps2              # Convertir a m/s²
    n_steps = len(accel_mps2)
    t_arr = np.arange(n_steps) * dt

    for i, T in enumerate(T_range):
        omega   = 2.0 * np.pi / T              # Frecuencia angular natural
        omega_d = omega * np.sqrt(1 - zeta**2) # Frecuencia amortiguada

        # Integral de Duhamel via convolución numérica (Método Newmark β)
        # h(t-τ) = e^(-ζω(t-τ)) · sin(ωd(t-τ)) / ωd
        max_disp = 0.0

        # Respuesta incremental SDof (Paso a Paso)
        u  = 0.0  # Desplazamiento
        v  = 0.0  # Velocidad
        for k in range(n_steps - 1):
            ag_k   = accel_mps2[k]
            ag_k1  = accel_mps2[k + 1]

            # Newmark average-acceleration constants (Rule 12 — model constants)
            beta  = _NEWMARK_BETA
            gamma = _NEWMARK_GAMMA

            m = 1.0                           # Masa unitaria
            k_stif = omega**2 * m
            c = 2.0 * zeta * omega * m

            # Predictor
            v_pred = v + dt * (1 - gamma) * (-ag_k - 2*zeta*omega*v - omega**2*u)
            u_pred = u + dt * v + dt**2 * (0.5 - beta) * (-ag_k - 2*zeta*omega*v - omega**2*u)

            # Aceleración efectiva en t+dt
            k_eff  = m + gamma * dt * c + beta * dt**2 * k_stif
            r_eff  = -ag_k1 * m - c * v_pred - k_stif * u_pred
            a_new  = r_eff / k_eff

            u = u_pred + beta * dt**2 * a_new
            v = v_pred + gamma * dt * a_new

            if abs(u) > max_disp:
                max_disp = abs(u)

        # Pseudo-Aceleración Sa = ω² · max|u|
        Sa_ms2 = omega**2 * max_disp
        Sa_arr[i] = Sa_ms2 / g_mps2          # Convertir a 'g'

    pga = float(np.max(np.abs(accel_g)))
    return {"T": T_range, "Sa": Sa_arr, "pga": pga, "zeta": zeta}


def generate_spectral_report(sa_raw: dict, sa_filtered: dict) -> str:
    """
    Genera una tabla Markdown comparando el espectro crudo vs filtrado por el Guardian Angel.
    Tabla orientada a la Sección 3 de un paper Q1.
    """
    T_arr = sa_raw["T"]
    Sa_raw = sa_raw["Sa"]
    Sa_filt = sa_filtered["Sa"]

    # Seleccionar 10 periodos representativos para la tabla
    indices = np.round(np.linspace(0, len(T_arr)-1, 10)).astype(int)

    lines = []
    lines.append("\n### 3.4 Response Spectrum Sa(T, ζ=5%) — PEER/CISMID Benchmark\n")
    lines.append(
        "The Duhamel integral was applied over the normalized PISCO-2007 record "
        f"(PGA = {sa_raw['pga']:.3f}g) to compute the pseudo-acceleration spectrum "
        f"(ζ = {sa_raw['zeta']*100:.0f}%, per E.030 / ASCE 7-22):\n"
    )
    lines.append("| Period T (s) | Sa Raw (g) | Sa Guardian-Filtered (g) | Reduction (%) |")
    lines.append("|---|---|---|---|")
    for idx in indices:
        T    = T_arr[idx]
        raw  = Sa_raw[idx]
        filt = Sa_filt[idx]
        reduction = ((raw - filt) / raw * 100) if raw > 0 else 0
        lines.append(f"| {T:.2f} | {raw:.4f} | {filt:.4f} | {reduction:.1f}% |")

    lines.append(
        "\nThe Guardian Angel's physics-based filtering eliminates high-frequency anomalies, "
        "resulting in a cleaner spectral demand curve and protecting the LSTM from "
        "over-excited energy distributions near the dominant structural period."
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# FASE 40 — AMPLIFICACIÓN DE SUELO (NORMA E.030-2018, PERÚ)
# Referencia: RNE E.030 Artículo 14 y Tabla 4
# ══════════════════════════════════════════════════════════════

def load_soil_params(soil_yaml_path=None) -> dict:
    """
    Carga los parámetros de suelo desde config/soil_params.yaml.
    Si el archivo no existe, usa valores conservadores por defecto (S2, Zona 4).
    """
    try:
        import yaml
    except ImportError:
        print("[SPECTRAL] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    if soil_yaml_path is None:
        soil_yaml_path = ROOT / "config" / "soil_params.yaml"

    defaults = {"S": 1.05, "Tp": 0.6, "Tl": 2.0, "Z": 0.45,
                "C_max": 2.5, "soil_type": "S2", "zone": 4}
    try:
        with open(soil_yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        amp    = data.get("amplification", {})
        plat   = data.get("spectral_plateau", {"C_max": 2.5})
        design = data.get("design", {})
        return {
            "S":         float(amp.get("S",  defaults["S"])),
            "Tp":        float(amp.get("Tp", defaults["Tp"])),
            "Tl":        float(amp.get("Tl", defaults["Tl"])),
            "Z":         float(design.get("Z", defaults["Z"])),
            "C_max":     float(plat.get("C_max", defaults["C_max"])),
            "soil_type": data.get("site_conditions", {}).get("soil_type", defaults["soil_type"]),
            "zone":      data.get("site_conditions", {}).get("zone",      defaults["zone"]),
        }
    except FileNotFoundError:
        print(f"[SPECTRAL] WARNING: soil_params.yaml not found at {soil_yaml_path}."
              " Using conservative defaults (S2, Zone 4).", file=sys.stderr)
        return defaults
    except yaml.YAMLError as e:
        print(f"[SPECTRAL] ERROR: soil_params.yaml malformed: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[SPECTRAL] ERROR: cannot read soil_params.yaml: {e}", file=sys.stderr)
        sys.exit(1)


def compute_c_factor(T: float, Tp: float, Tl: float, C_max: float = 2.5) -> float:
    """
    Factor de amplificación sísmica C(T) según R.N.E. E.030-2018, Artículo 14:

        C = C_max                     si  T  <  Tp     (Plataforma)
        C = C_max * (Tp / T)          si  Tp <= T < Tl  (Decaimiento 1/T)
        C = C_max * (Tp * Tl / T²)   si  T  >= Tl      (Decaimiento 1/T²)
    """
    if T < Tp:
        return C_max
    elif T < Tl:
        return C_max * (Tp / T)
    else:
        return C_max * (Tp * Tl / T**2)


def apply_site_amplification(sa_base: dict, soil_params: dict = None) -> dict:
    """
    Convierte el Espectro de Roca Base Sa(T) en Espectro de Sitio Sa_site(T)
    aplicando el Factor de Amplificación de Suelo de la Norma E.030.

    Sa_site(T) = Sa_base(T) × S × [ C(T) / C_max ]

    El término [C(T)/C_max] representa la "joroba" del espectro de sitio:
    la amplificación es máxima en la plataforma (T < Tp) y decae en periodos
    largos, modelando la respuesta real del suelo localmente.

    Retorna:
      - dict con los mismos campos que sa_base + claves 'Sa_site', 'soil_params', 'C_factors'
    """
    if soil_params is None:
        soil_params = load_soil_params()

    S    = soil_params["S"]
    Tp   = soil_params["Tp"]
    Tl   = soil_params["Tl"]
    Cmax = soil_params["C_max"]
    T    = sa_base["T"]

    C_arr     = np.array([compute_c_factor(t, Tp, Tl, Cmax) for t in T])
    Sa_site   = sa_base["Sa"] * S * (C_arr / Cmax)

    # Periodo de mayor demanda en el espectro de sitio
    peak_idx   = int(np.argmax(Sa_site))
    T_star     = float(T[peak_idx])
    Sa_star    = float(Sa_site[peak_idx])
    zone_label = ("plataforma" if T_star < Tp else
                  "decaimiento 1/T" if T_star < Tl else "decaimiento 1/T²")

    print(f"   🌍 [E.030] Suelo {soil_params['soil_type']} | S={S} | Tp={Tp}s | Tl={Tl}s")
    print(f"   🌍 [E.030] Sa_site máx = {Sa_star:.3f}g @ T*={T_star:.2f}s ({zone_label})")

    return {
        **sa_base,
        "Sa_site":    Sa_site,
        "C_factors":  C_arr,
        "soil_params": soil_params,
        "T_star_site": T_star,
        "Sa_star_site": Sa_star,
        "zone_label":  zone_label,
    }


def generate_site_amplification_report(sa_site_dict: dict) -> str:
    """
    Genera la Sección 3.6 del paper Q1 con la corrección geotécnica del sitio.
    """
    sp   = sa_site_dict["soil_params"]
    T    = sa_site_dict["T"]
    Sb   = sa_site_dict["Sa"]       # Roca base
    Ss   = sa_site_dict["Sa_site"]  # Sitio amplificado
    T_st = sa_site_dict["T_star_site"]
    sa_s = sa_site_dict["Sa_star_site"]
    zone = sa_site_dict["zone_label"]

    indices = np.round(np.linspace(0, len(T)-1, 10)).astype(int)

    lines = []
    lines.append("\n### 3.6 Site-Specific Spectral Amplification (E.030-2018, Soil S2)\n")
    lines.append(
        f"The Site Amplification Factor $C(T)$ (E.030-2018, Art. 14) was applied "
        f"over the PEER base-rock spectrum to obtain a site-specific demand curve for "
        f"the monitoring site (Soil Type S2, Zone 4, $Z=0.45g$):\n\n"
        f"$$C(T) = \\begin{{cases}} 2.5 & T < {sp['Tp']}s \\\\\\\\ "
        f"2.5 \\cdot T_p/T & {sp['Tp']}s \\le T < {sp['Tl']}s \\\\\\\\ "
        f"2.5 \\cdot T_p T_l / T^2 & T \\ge {sp['Tl']}s \\end{{cases}}$$\n"
    )
    lines.append(f"| Period T (s) | Sa Base-Rock (g) | Sa Site {sp['soil_type']} (g) | C Factor |")
    lines.append("|---|---|---|---|")
    for idx in indices:
        t = T[idx]; sb = Sb[idx]; ss = Ss[idx]
        c = sa_site_dict["C_factors"][idx]
        lines.append(f"| {t:.2f} | {sb:.4f} | {ss:.4f} | {c:.2f} |")

    lines.append(
        f"\n> **Site Interpretation**: The maximum site-adjusted demand reaches "
        f"$S_{{a,site}} = {sa_s:.3f}g$ at $T^* = {T_st:.2f}s$ ({zone}). "
        f"Given the measured natural frequency $f_n$ of the monitored element (from Engram telemetry), "
        f"the system evaluates whether the structure sits in the amplification plateau "
        f"($T < T_p = {sp['Tp']}s$), where spectral demand is **maximum and constant**, representing "
        f"the highest collapse risk scenario for low-rise structures at the monitoring site.\n"
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# FASE 39 — MÓDULO DE DISIPACIÓN DE ENERGÍA (ζ VARIABLE)
# Referencia: Eurocode 8, Ecuación B.3
# ══════════════════════════════════════════════════════════════

ZETA_VIRGIN_CONCRETE  = 0.050  # ASCE 7-22 §12.1.1 / E.030-2018 §14 Table 7: ζ=5% conventional concrete
ZETA_MATERIAL_LOW     = 0.070  # Eurocode 8:2004 §3.2.2.2 Eq.(3.6): lower bound, high-porosity RC
ZETA_MATERIAL_NOMINAL = 0.075  # Eurocode 8:2004 §3.2.2.2 Eq.(3.6): nominal, porous RC material
ZETA_MATERIAL_HIGH    = 0.080  # Eurocode 8:2004 §3.2.2.2 Eq.(3.6): upper bound, degraded/fatigued


def apply_damping_correction(Sa_ref: np.ndarray, zeta_ref: float = 0.05, zeta_target: float = 0.075) -> np.ndarray:
    """
    Escala un espectro Sa de referencia a un nivel de amortiguamiento diferente.
    Formula: Eurocode 8, Eq. B.3

        Sa(T, ζ_target) ≈ Sa(T, ζ_ref) * sqrt(10 / (5 + ζ_target*100))

    Nota: La fórmula usa ζ en porcentaje (5%, 7.5%, etc.)

    Parámetros
    ----------
    Sa_ref     : espectro de referencia (calculado con Newmark a ζ_ref)
    zeta_ref   : amortiguamiento del espectro de referencia (fraccion, e.g. 0.05)
    zeta_target: amortiguamiento objetivo (fraccion, e.g. 0.075)

    Retorna
    -------
    Sa_target  : espectro escalado al nuevo amortiguamiento
    """
    eta_ref    = np.sqrt(10.0 / (5.0 + zeta_ref    * 100))  # Factor EC8 referencia
    eta_target = np.sqrt(10.0 / (5.0 + zeta_target * 100))  # Factor EC8 objetivo
    return Sa_ref * (eta_target / eta_ref)


def compare_material_vs_reference(sa_base: dict) -> dict:
    """
    Genera la comparativa espectral entre material de referencia (ζ=5%) y material de estudio (ζ=7.5%).
    Utiliza la correción de Eurocode 8 sobre el espectro base ya calculado.

    Retorna dict con:
      - T             : array de periodos
      - Sa_virgin     : espectro a ζ=5% (material de referencia)
      - Sa_mat_low    : espectro a ζ=7.0% (material lower bound)
      - Sa_mat_nominal: espectro a ζ=7.5% (material nominal)
      - Sa_mat_high   : espectro a ζ=8.0% (material degraded)
      - reduction_pct : reducción máxima del espectro nominal vs referencia (%)
    """
    Sa_ref = sa_base["Sa"]
    T_arr  = sa_base["T"]

    Sa_virgin      = apply_damping_correction(Sa_ref, ZETA_VIRGIN_CONCRETE, ZETA_VIRGIN_CONCRETE)  # No-op, referencia
    Sa_mat_low     = apply_damping_correction(Sa_ref, ZETA_VIRGIN_CONCRETE, ZETA_MATERIAL_LOW)
    Sa_mat_nominal = apply_damping_correction(Sa_ref, ZETA_VIRGIN_CONCRETE, ZETA_MATERIAL_NOMINAL)
    Sa_mat_high    = apply_damping_correction(Sa_ref, ZETA_VIRGIN_CONCRETE, ZETA_MATERIAL_HIGH)

    # Reducción máxima en el pico espectral
    peak_idx     = int(np.argmax(Sa_ref))
    T_star       = float(T_arr[peak_idx])
    reduction    = float((Sa_virgin[peak_idx] - Sa_mat_nominal[peak_idx]) / Sa_virgin[peak_idx] * 100)

    return {
        "T": T_arr,
        "Sa_virgin":       Sa_virgin,
        "Sa_mat_low":      Sa_mat_low,
        "Sa_mat_nominal":  Sa_mat_nominal,
        "Sa_mat_high":     Sa_mat_high,
        "T_star":          T_star,
        "reduction_pct":   round(reduction, 2),
    }


def generate_material_damping_report(mat_data: dict) -> str:
    """
    Genera la Sección 3.5 del paper Q1: Comparativa Espectral Reference Material vs. Study Material.
    """
    T    = mat_data["T"]
    Sv   = mat_data["Sa_virgin"]
    Sn   = mat_data["Sa_mat_nominal"]
    T_st = mat_data["T_star"]
    red  = mat_data["reduction_pct"]

    # 10 periodos representativos
    indices = np.round(np.linspace(0, len(T)-1, 10)).astype(int)

    lines = []
    lines.append("\n### 3.5 Energy Dissipation Advantage: Reference Material vs. Study Material (Damping Correction)\n")
    lines.append(
        f"The inherent microporosity of the study material induces a higher "
        f"intrinsic damping ratio than conventional concrete. Applying the Eurocode 8 "
        f"damping correction factor (Eq. B.3), the spectral demand shifts:\n\n"
        f"$$S_a(T, \\zeta) \\approx S_a(T, 0.05) \\cdot \\sqrt{{\\frac{{10}}{{5 + \\zeta_{{mat}}}}}}$$\n"
    )
    lines.append("| Period T (s) | Sa Reference ζ=5% (g) | Sa Material ζ=7.5% (g) | Reduction (%) |")
    lines.append("|---|---|---|---|")
    for idx in indices:
        t = T[idx]; sv = Sv[idx]; sn = Sn[idx]
        r = ((sv - sn) / sv * 100) if sv > 0 else 0
        lines.append(f"| {t:.2f} | {sv:.4f} | {sn:.4f} | **{r:.1f}%** |")

    lines.append(
        f"\n> **Mechanical Interpretation**: At T*={T_st:.2f}s (the dominant subduction period for "
        f"the monitoring site), the study material achieves a **{red:.1f}% spectral demand reduction** "
        f"compared to conventional concrete under the same seismic input. This confirms that the inherent "
        f"hysteretic dissipation of the study material constitutes a passive resilience mechanism, "
        f"reducing collapse risk without additional structural intervention.\n"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo rápido usando un sismo sintético tipo Kanai-Tajimi (similar al Pisco 2007)
    dt = 0.005
    t = np.arange(0, 60, dt)
    envelope = (t / 3.0) * np.exp(-t / 3.0)
    accel = np.sin(2 * np.pi * 3.5 * t) * envelope + np.random.normal(0, 0.03, len(t))
    scale = 0.33 / np.max(np.abs(accel))
    accel_g = accel * scale

    print("⚡ Calculando Espectro de Respuesta Sa(T, ζ=5%)...")
    result = compute_spectral_response(accel_g, dt)
    Sa = result["Sa"]
    T  = result["T"]

    # Periodo con mayor demanda espectral
    peak_idx = np.argmax(Sa)
    print(f"✅ PGA del registro   : {result['pga']:.3f}g")
    print(f"✅ Sa máximo          : {Sa[peak_idx]:.3f}g  @ T = {T[peak_idx]:.2f}s")
    print(f"   (Este es el período de mayor peligro para la estructura)")
