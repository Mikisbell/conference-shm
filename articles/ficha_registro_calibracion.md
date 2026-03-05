# FICHA DE REGISTRO METROLÓGICO: LÍNEA BASE Y DESPLIEGUE INICIAL
**Proyecto:** Bélico Stack — Auditoría Estructural C&DW
**Ubicación:** Presa del Norte "La Esperanza"

> **Instrucción de Campo:** Este documento debe ser llenado a mano (o digitalmente in-situ) el **Día Cero** de la instalación. Es la primera pieza de evidencia pericial antes de que el *Guardian Angel* asuma el control autónomo.

---

## 1. Identificación del Hardware (Edge Node)
*   **Fecha de Instalación:** `[YYYY-MM-DD]`
*   **Hora Inicial (Local):** `[HH:MM]`
*   **Column/Element ID:** `[Ej: A-12]`
*   **MAC Address / ID Nicla:** `________________________`
*   **Frecuencia LoRa Configurada:** `[915 MHz / CH 0x0D]`
*   **Potencia de TX:** `[30 dBm]`
*   **Batería Inicial (V):** `[Ej: 4.15 V]`

## 2. Condiciones Ambientales (Baseline Pasivo)
*Notas meteorológicas durante los 30 min de silencio del `baseline_calibration.py`.*
*   **Clima:** `[Soleado | Nublado | Lluvia | Viento Fuerte]`
*   **Temperatura Externa Aprox:** `[_____ °C]`
*   **Operación de la Presa:** `[Turbinas encendidas | Vertedero activo | Silencio]`

## 3. Resultados de Calibración Matemática 
*Valores extraídos de `config/field_baseline.yaml` tras los 30 min de escucha.*
*   **Frecuencia Natural Base ($f_n$):** `[________ Hz]`
*   **Ruido Vibracional $\sigma$:** `[± _______ Hz]`
*   **Max G (Fondo):** `[________ g]`
*   **RSSI Mediana (Señal):** `[________ dBm]` a una distancia de `[____ km]`

### Hash de Integridad Inicial
Anota los primeros 8 caracteres del `config_hash` reportado por el Bridge al arrancar, para vincular este papel físico con el código exacto que estaba corriendo:
*   `SSOT Config Hash:` `________________`

## 4. Firmas de Cadena de Custodia
Declaro que la calibración se realizó sin intervención física sobre el muro y que el sistema arrancó en estado `SANO` y sellando el primer bloque en el *Engram*.

*   **Ingeniero / Auditor Principal:** ___________________________
*   **Firma:** ___________________________

---
*Fin del documento.*
