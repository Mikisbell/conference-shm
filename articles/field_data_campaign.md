# Field Data Campaign Protocol — Belico Stack
# Objetivo: recopilar 30+ min de datos continuos para papers Q3/Q4 y Q1

## 1. Hardware Checklist

### Nodo Edge (x2 nodos minimo para redundancia)
| Componente | Modelo | Qty | Estado | Notas |
|------------|--------|-----|--------|-------|
| MCU + IMU | Arduino Nicla Sense ME (BHI260AP) | 2 | [ ] | Firmware: `nicla_edge_field.ino` flasheado con params.h actual |
| MCU alternativo | Arduino Nano 33 BLE Sense Rev2 (BMI270) | 1 | [ ] | Firmware: `nano33_belico.ino`, conexion USB directa |
| Transceptor LoRa | E32-915T30D (30dBm, 915MHz) | 2 | [ ] | Antena 5dBi minimo, SMA macho |
| Bateria | LiPo 3.7V 2000mAh | 2 | [ ] | Carga completa >3.9V verificada con multimetro |
| Cargador | TP4056 con proteccion | 2 | [ ] | Verificar LED verde (carga completa) |
| Step-Up | 3.7V -> 5.1V (para E32 VCC) | 2 | [ ] | Salida >600mA para pico TX del E32 |
| Capacitor | 1000uF electrolítico entre VCC/GND del E32 | 2 | [ ] | Absorbe pico de corriente en TX |
| Caja estanca | IP65 PVC ~120x80x50mm | 2 | [ ] | Con orificio para antena SMA |
| Montaje | Epóxido estructural + base magnética | 2 | [ ] | Superficie limpia, sin pintura suelta |

### Gateway / Base
| Componente | Modelo | Qty | Estado | Notas |
|------------|--------|-----|--------|-------|
| Laptop | Linux (WSL2 o nativo) con Python 3.10+ | 1 | [ ] | belico-stack clonado y venv activo |
| Receptor LoRa | E32-915T30D + USB-UART (CP2102/CH340) | 1 | [ ] | Verificar puerto con `ls /dev/ttyUSB*` |
| Antena gateway | 8dBi omnidireccional 915MHz | 1 | [ ] | Elevada >2m sobre el suelo |
| Cable USB | USB-C (Nicla) o Micro-USB (Nano33) | 2 | [ ] | Para modo cableado directo (backup) |
| Power bank | 20000mAh | 1 | [ ] | Para laptop si no hay corriente en sitio |

### Instrumentacion de Referencia (opcional, mejora el paper)
| Componente | Uso | Notas |
|------------|-----|-------|
| Acelerómetro de referencia (PCB Piezotronics / ADXL355) | Ground truth | Montaje colineal con el nodo Belico |
| Martillo de Schmidt | Impacto controlado para test RL2 | Ya en field_test_protocol.md Test 4 |
| Termómetro IR | Verificar temperatura de superficie | Comparar con BME688/HS3003 del nodo |
| GPS handheld o smartphone | Geolocalización precisa del nodo | Para metadatos de la campaña |

---

## 2. Software Pre-Campaign Checklist

```bash
# 1. Regenerar params.h con hash actual
python tools/generate_params.py
# Verificar: src/firmware/params.h tiene CONFIG_HASH correcto

# 2. Flashear firmware al nodo
# Arduino IDE: abrir nicla_edge_field.ino, verificar #include "params.h", Upload

# 3. Verificar bridge.py conectividad
python src/bridge.py --port /dev/ttyUSB0 --test
# Esperar: HANDSHAKE OK, primeros 10 paquetes parseados

# 4. Verificar Engram operativo
engram stats
# Esperar: database path correcto

# 5. Calibracion baseline (si no existe o tiene >7 dias)
python tools/baseline_calibration.py --duration 60 --output config/field_baseline.yaml
# Actualiza fn_baseline_hz, max_g_ambient, guardian thresholds

# 6. Verificar espacio en disco
df -h /home/mateo/PROYECTOS/belico-stack/data/
# Necesario: >500MB libres (30min @ 100Hz ~ 18MB CSV + Engram)
```

---

## 3. Measurement Protocol

### 3.1 Ubicacion del Sensor
- **Sitio**: Estructura RC con componente C&DW (columna, viga, o losa)
- **Posicion**: A 2/3 de la altura del elemento (zona de máxima deformación lateral)
- **Orientación**: Eje X del sensor alineado con dirección transversal débil
- **Fijación**: Epóxido estructural o base magnética (superficie preparada con lija 80)
- **Distancia nodo-gateway**: Registrar en metros. Máximo recomendado: 2km con LOS

### 3.2 Sesiones de Adquisicion

| Sesion | Duracion | Objetivo | Datos esperados |
|--------|----------|----------|-----------------|
| S1: Ambient vibration | 30 min continuo | Línea base fn, caracterización modal | ~180,000 muestras @ 100Hz |
| S2: Impacto controlado | 10 min (5 impactos) | Respuesta transitoria, validación RL2 | Picos de 0.3-0.5g |
| S3: Ciclo térmico | 4 horas (automatico) | Deriva térmica diurna | Temperatura 20-60°C |
| S4: Nocturno (opcional) | 8 horas | Ruido mínimo, fn de referencia pura | fn con <0.01g RMS |

**Sesion S1 es OBLIGATORIA** — es el dato mínimo para los papers Q3/Q4.

### 3.3 Procedimiento Sesion S1 (Ambient Vibration — 30 min)

1. **T-15min**: Instalar nodo, encender, verificar LED verde
2. **T-10min**: Encender gateway, ejecutar:
   ```bash
   python src/bridge.py --port /dev/ttyUSB0 --log data/raw/field_S1_$(date +%Y%m%d).csv
   ```
3. **T-5min**: Verificar primeros paquetes en consola. Confirmar:
   - `STAT:OK` en todos los paquetes
   - `fn` dentro de ±0.5Hz del baseline (field_baseline.yaml)
   - `RSSI > -110 dBm` (si es LoRa)
4. **T=0**: Iniciar cronómetro. **NO tocar nada durante 30 minutos.**
   - Alejarse >5m del nodo para evitar vibración de pisadas
   - Registrar condiciones: viento (escala Beaufort), tráfico, obras cercanas
5. **T+30min**: Detener bridge.py (`Ctrl+C` limpio)
6. **Verificar datos**:
   ```bash
   wc -l data/raw/field_S1_*.csv       # Esperar: >180,000 lineas
   python -c "
   import pandas as pd
   df = pd.read_csv('data/raw/field_S1_$(date +%Y%m%d).csv')
   print(f'Muestras: {len(df)}')
   print(f'Duracion: {(df.iloc[-1].T - df.iloc[0].T)/1000:.1f}s')
   print(f'Gaps > 50ms: {(df.T.diff() > 50).sum()}')
   "
   ```
7. **Registrar en Engram**:
   ```bash
   engram add "Field campaign S1 complete: $(wc -l < data/raw/field_S1_*.csv) samples, site=$(grep site config/field_baseline.yaml | cut -d: -f2)" --tag field_campaign
   ```

### 3.4 Metadata por Sesion

Crear un archivo `data/raw/field_S1_YYYYMMDD_meta.yaml` con:

```yaml
session: S1
date: YYYY-MM-DD
time_start: "HH:MM:SS"
time_end: "HH:MM:SS"
site: "La Presa del Norte"
gps: "lat, lon"
element: "Columna C-12, 3er piso"
material: "C&DW 20MPa, 30% agregado reciclado"
node_id: "nicla_01"
firmware: "nicla_edge_field.ino"
config_hash: "3dd726ee4864d752"  # from params.h
weather:
  temperature_c: 28
  humidity_pct: 65
  wind_beaufort: 2
  precipitation: none
  notes: "Tráfico vehicular moderado a 50m"
observer: "M. Mikisbell"
```

---

## 4. Post-Campaign Data Processing

```bash
# 1. Copiar datos crudos a processed/
cp data/raw/field_S1_*.csv data/processed/

# 2. Ejecutar pipeline completo
python src/bridge.py --replay data/processed/field_S1_*.csv  # Guardian Angel + Engram

# 3. Generar figuras para el paper
python tools/plot_conference_figures.py --field-data data/processed/field_S1_*.csv

# 4. Ejecutar PgNN surrogate sobre datos reales
python -c "
from src.ai.pgnn_surrogate import PgNNSurrogate
import pandas as pd
df = pd.read_csv('data/processed/field_S1_YYYYMMDD.csv')
pgnn = PgNNSurrogate()
result = pgnn.predict_with_alarm(df['accel_g'].values)
print(f'Max IDR: {result[\"idr\"].max():.4f}')
print(f'Alarm: {result[\"alarm\"]}')
print(f'Latency: {result[\"latency_ms\"]:.1f}ms')
"

# 5. Snapshot de Engram post-campaign
engram stats
```

---

## 5. Data Requirements per Paper Level

| Paper | Sesion minima | Datos adicionales | Estado |
|-------|--------------|-------------------|--------|
| Conference (EWSHM 2026) | Synthetic only | cv_results.json ya existe | LISTO |
| Q3/Q4 Journal | S1 (30 min ambient) | + spectral analysis real | PENDIENTE |
| Q2 Journal | S1 + S2 (impact) | + PgNN inference on real data | PENDIENTE |
| Q1 Journal | S1 + S2 + S3 + S4 | + LSTM TTF with N>=30 Engram records | PENDIENTE |

---

## 6. Risk Mitigation

| Riesgo | Mitigación |
|--------|------------|
| Bateria muere antes de 30min | LiPo 2000mAh dura >6h con duty cycle. Verificar V>3.5V pre-test |
| LoRa pierde paquetes (>10%) | Reducir distancia o elevar antena. Backup: modo USB directo con Nano33 |
| Lluvia durante sesion | Caja IP65 protege nodo. Gateway bajo toldo. No cancelar por lluvia ligera |
| Vibración de tráfico enmascara fn | Sesion S4 nocturna como control. O filtrar banda >20Hz en post-proceso |
| fn real difiere >20% del modelo | Actualizar params.yaml con fn medido. Recalibrar Guardian Angel thresholds |
| Daño al nodo durante instalacion | Nodo de respaldo (2 unidades de cada componente) |
