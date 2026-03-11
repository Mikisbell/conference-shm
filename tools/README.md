# Parser Belico — Protocolo de Generacion de Parametros

## Proposito

Este directorio contiene las herramientas que **leen `config/params.yaml`** (la SSOT) y generan los archivos de parametros para cada dominio de ejecucion.

**Regla:** Nunca edites `src/firmware/params.h` ni `src/physics/models/params.py` directamente. Siempre trabaja en `config/params.yaml` y regenera.

---

## Flujo de Generacion

```
config/params.yaml   (SSOT — unica fuente de verdad)
         |
         +---> tools/generate_params.py
         |           |
         |           +---> src/firmware/params.h        (C++ para Arduino)
         |           +---> src/physics/models/params.py (Python para OpenSeesPy)
         |
         +---> config_hash.sha256   (hash del YAML — validado por Verifier)
```

---

## Archivos Generados

### `src/firmware/params.h`
Header de C++ con `#define` para cada parametro. Arduino lo incluye con `#include "params.h"`.

Ejemplo de output esperado:
```c
// AUTO-GENERATED — NO EDITAR DIRECTAMENTE
// Fuente: config/params.yaml | Hash: [sha256]
#define STIFFNESS_K    5000.0f   // N/m
#define MASS_M         1000.0f   // kg
#define DAMPING_RATIO  0.05f     // dimensionless
#define SAMPLE_RATE_HZ 100       // Hz
#define SENSOR_PIN     A0
#define SERIAL_BAUD    115200
```

### `src/physics/models/params.py`
Modulo Python con un diccionario de parametros. OpenSeesPy lo importa con `from src.physics.models.params import P`.

Ejemplo de output esperado:
```python
# AUTO-GENERATED — NO EDITAR DIRECTAMENTE
# Fuente: config/params.yaml | Hash: [sha256]
CONFIG_HASH = "[sha256]"
P = {
    "E":    200e9,    # Pa
    "fy":   250e6,    # Pa
    "k":    5000.0,   # N/m
    "mass": 1000.0,   # kg
    "xi":   0.05,     # dimensionless
    "dt":   0.01,     # s (1/sample_rate_hz)
}
GUARDRAILS = {
    "max_stress_ratio":        0.6,
    "convergence_tolerance":   1e-6,
    "max_slenderness":         120,
    "eccentricity_ratio":      0.10,
    "mass_participation_min":  0.90,
    "max_sensor_outlier_sigma": 3.0,
}
```

---

## Como Usar

```bash
# Desde la raiz del repo
python tools/generate_params.py

# El script reporta:
# src/firmware/params.h generado
# src/physics/models/params.py generado
# config_hash.sha256 actualizado: [hash]
```

---

## Validacion del Verifier (PASO 4-bis: Hash de Configuracion)

El sub-agente Verifier compara el hash del `params.yaml` en el momento de la simulacion contra el hash embebido en `params.py`. Si no coinciden:

> **ERROR DE FUENTE DE VERDAD — CONFIGURACION DESINCRONIZADA**
> El firmware y la simulacion estan usando parametros de versiones distintas.
> Accion: Ejecutar `python tools/generate_params.py` y repetir la simulacion.

---

## Style Calibration

### Proposito

Calibra la voz del narrador con papers reales del venue target **antes de IMPLEMENT**. El script busca papers publicados en el venue objetivo, extrae patrones de escritura (voz, tiempo verbal, densidad de citas, longitud de oraciones, conectores tipicos) y genera un Style Card que `scientific_narrator.py` consume automaticamente al escribir cada batch.

Sin Style Calibration, el narrador escribe con voz generica detectable como IA. Con Style Calibration, el draft imita la voz de autores reales del mismo venue.

### Prerequisito

- **Obligatorio** antes de IMPLEMENT Batch 1 para papers Q1 y Q2.
- **Recomendado** para todos los quartiles (Conference, Q3, Q4).
- `validate_submission.py` Gate 0.7 bloquea la compilacion de Q1/Q2 si `data/processed/style_card.json` no existe.

### Comando

```bash
python3 tools/style_calibration.py \
  --venue "{venue name}" \
  --paper-id {paper_id} \
  [--year {year}] \
  [--n {n_papers}] \
  [--save-md] \
  [--dry-run]
```

**Argumentos:**

| Argumento | Descripcion | Default |
|-----------|-------------|---------|
| `--venue` | Nombre del venue target (ej: "EWSHM", "Earthquake Engineering & Structural Dynamics") | requerido |
| `--paper-id` | ID del paper activo (ej: `icr_shm_ae_conference`) | requerido |
| `--year` | Ano de referencia para buscar papers del venue | ano actual |
| `--n` | Numero de papers a analizar | 5 |
| `--save-md` | Guarda Style Card como `articles/drafts/style_card_{paper_id}.md` | desactivado |
| `--dry-run` | Muestra que haria sin ejecutar busquedas ni escribir archivos | desactivado |

**Ejemplo:**
```bash
python3 tools/style_calibration.py \
  --venue "EWSHM" \
  --year 2024 \
  --n 5 \
  --paper-id icr_shm_ae_conference \
  --save-md
```

### Outputs

El script genera tres salidas en una sola ejecucion:

1. **Engram (siempre):**
   ```
   mem_save("style: {paper_id} — venue={venue}, voice={voice}, citation_density={N}/para, avg_sentence_len={N}w, opener_pattern={pattern}")
   ```

2. **`data/processed/style_card.json` (siempre):**
   JSON con el Style Card completo. `scientific_narrator.py` lo lee **automaticamente** al inicio de `generate_paper()` — el orquestador no necesita inyectarlo en el prompt del narrator.

3. **`articles/drafts/style_card_{paper_id}.md` (solo con `--save-md`):**
   Version legible del Style Card para revision humana y lectura directa por sub-agentes.

### Gate

`validate_submission.py` Gate 0.7 verifica la existencia de `data/processed/style_card.json` para papers Q1 y Q2. Si el archivo no existe:

```
[GATE 0.7 FAIL] style_card.json not found in data/processed/
Q1/Q2 papers require Style Calibration before submission.
Run: python3 tools/style_calibration.py --venue "{venue}" --paper-id {paper_id}
```

### Integracion con scientific_narrator.py

`scientific_narrator.py` carga `data/processed/style_card.json` automaticamente al inicio de `generate_paper()`. El Style Card controla:
- Voz (activa/pasiva por seccion)
- Densidad de citas por parrafo
- Longitud promedio de oraciones
- Patrones de apertura de parrafo
- Conectores permitidos (venue-appropriate, no AI-detectable)

El orquestador **NO necesita** inyectar el Style Card en el prompt del narrator. La lectura es automatica via el JSON en disco.
