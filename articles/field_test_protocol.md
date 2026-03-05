# Protocolo de Pruebas de Estrés de Campo — Belico Stack
*Ejecutar antes de declarar el sistema operativo en La Presa del Norte*

## Test 1: Penetración en Concreto C&DW (Alcance LoRa Real)
**Objetivo**: Verificar link budget con muro de 1m de concreto reciclado a 2 km.

**Procedimiento**:
1. Instalar nodo (Nicla+E32) detrás de muro C&DW de 1m de espesor.
2. Gateway LoRa en laptop a 2 km de distancia (línea de vista parcial).
3. Correr `bridge.py` y observar RSSI en consola.
4. Registrar en Engram con tag `field_test_penetration`.

**Criterio de Éxito**: RSSI > -120 dBm y ≥ 90% de paquetes recibidos en 30min.

**Nota**: Si RSSI < -120 dBm, subir antena de 5 a 8 dBi o reposicionar gateway.

---

## Test 2: Deriva Térmica (Guardian Angel vs. Calor Solar)
**Objetivo**: Confirmar que el calor solar (~60°C en caja estanca) no dispara falsa alarma.

**Procedimiento**:
1. Colocar nodo en caja PVC estanca al sol de mediodía por 4 horas.
2. Monitorear Engram: verificar que NO aparezcan tags `physics_violation` ni `alarm`.
3. Si aparecen entradas `GUARDIAN_ANGEL_EXTREME_EVENT` con S-2 (temperatura), ajustar `TEMP_MAX_C` en `bridge.py` a 85°C para entornos de alta insolación.

**Criterio de Éxito**: Cero alarmas estructurales falsas. Solo paquetes `STAT:OK`.

---

## Test 3: Resiliencia a Ruido RF en 915 MHz
**Objetivo**: Confirmar que el Watchdog descarta paquetes corruptos sin dañar Engram.

**Procedimiento**:
1. Encender walkie-talkies o radio AM/FM a 2m del gateway durante 10 min.
2. Verificar en consola de `bridge.py` que paquetes corruptos se loguean como `parse_error` y no ingresan a Engram.
3. Verificar que Engram NO tiene entradas de paquetes parciales.

**Criterio de Éxito**: Engram 100% íntegro. Todos los paquetes aceptados tienen SHA-256 válido.

---

## Test 4: Impacto Controlado — Disparo de RL2 (Martillo de Schmidt)
**Objetivo**: Confirmar latencia total desde impacto hasta BIM Rojo < 5 segundos.

**Procedimiento**:
1. Nodo instalado en columna de prueba. `bridge.py` y `scientific_narrator.py` corriendo.
2. Golpe controlado con martillo de Schmidt a ~0.5m del sensor.
3. Medir tiempo desde impacto hasta que `bim_exporter.py` genera JSON con `#e74c3c`.
4. Registrar latencia en `data/processed/field_test_impact.csv`.

**Criterio de Éxito**: JSON BIM rojo generado en < 5 segundos. STAT=ALARM_RL2 en Engram.

---

## Registro de Resultados

| Test | Fecha | Resultado | RSSI / Latencia | Observaciones |
|------|-------|-----------|-----------------|---------------|
| 1. Penetración C&DW | | | dBm | |
| 2. Deriva Térmica | | | °C max | |
| 3. Ruido RF | | | paquetes corruptos | |
| 4. Impacto RL2 | | | segundos | |

> Guardar este archivo completado como `articles/drafts/field_test_results.md` y commitearlo antes de la presentación pública.
