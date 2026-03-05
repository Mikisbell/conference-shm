"""
src/physics/peer_adapter.py — Adaptador de Bases de Datos Sísmicas (PEER NGA-West2)
===================================================================================
Este módulo actúa como el "Diccionario de Metadatos" y traductor universal.
Recibe archivos `.AT2` de la base de datos PEER NGA-West2 (o CISMID compatibles),
y extrae la Serie de Tiempo Normalizada (Teorema de Nyquist) para que el
Belico Stack (OpenSeesPy o el Emulador LoRa) pueda inyectarlos como aceleración real.

La estructura de un archivo NGA-West2 típico:
Line 1: Organización (e.g. PEER NGA STRONG MOTION DATABASE RECORD)
Line 2: Metadatos del Terremoto (Fecha, Magnitud, Estación)
Line 3: Tipo de Data (ACCELERATION) y Unidades (G, cm/s2)
Line 4: NPTS= [N] , DT= [dt] SEC
Line 5+: Datos científicos puros (usualmente en notación científica)
"""

import numpy as np
from pathlib import Path
from scipy.interpolate import interp1d

class PeerAdapter:
    def __init__(self, target_frequency_hz: float = 100.0):
        """
        :param target_frequency_hz: Frecuencia a la que se remuestreará (re-sample) el sismo
                                    para igualarlo a la tasa de adquisición del Arduino Nicla.
        """
        self.target_dt = 1.0 / target_frequency_hz
        self.target_freq = target_frequency_hz

    def read_at2_file(self, filepath: Path) -> dict:
        """
        Lee el archivo .AT2, extrae metadatos y retorna el arreglo de aceleraciones en G.
        """
        if not filepath.exists():
            raise FileNotFoundError(f"[PEER] Archivo no encontrado: {filepath}")

        with open(filepath, 'r') as f:
            lines = f.readlines()

        if len(lines) < 5:
            raise ValueError("[PEER] Formato de archivo .AT2 inválido o vacío.")

        # Metadatos básicos
        header_eq = lines[1].strip()
        
        # Extraer NPTS (Número de puntos) y DT (Paso temporal en segundos)
        line4 = lines[3].upper()
        try:
            # Format is typically "NPTS=  3930 , DT=  .01000 SEC"
            parts = line4.split(',')
            npts_part = parts[0].split('=')[1].strip()
            dt_part = parts[1].split('=')[1].replace('SEC', '').strip()
            npts = int(npts_part)
            dt = float(dt_part)
        except Exception as e:
            raise ValueError(f"[PEER] No se pudo parsear NPTS/DT en la línea 4: {line4} -> {e}")

        # Extraer array de datos (pueden venir múltiples columnas por línea)
        accel_data_g = []
        for line in lines[4:]:
            # Los números suelen venir separados por espacios
            valores = line.strip().split()
            for v in valores:
                try:
                    accel_data_g.append(float(v))
                except ValueError:
                    pass # ignora caracteres raros si los hay al final

        if len(accel_data_g) == 0:
            raise ValueError("[PEER] No se extrajeron datos de aceleración.")

        print(f"🌍 [PEER] Cargado: {header_eq[:50]}... | Puntos: {len(accel_data_g)} | dt original: {dt}s")

        return {
            "metadata": header_eq,
            "npts_original": len(accel_data_g),
            "dt_original": dt,
            "acceleration_g": np.array(accel_data_g, dtype=np.float64)
        }

    def normalize_and_resample(self, raw_data_dict: dict) -> np.ndarray:
        """
        Aplica el Teorema de Nyquist y remuestrea el sismo utilizando interpolación
        esplínica o lineal para que coincida con el reloj del Búnker Belico Stack.
        """
        dt_orig = raw_data_dict["dt_original"]
        npts_orig = raw_data_dict["npts_original"]
        accel_orig = raw_data_dict["acceleration_g"]

        # Vector de tiempo original
        time_orig = np.arange(0, npts_orig * dt_orig, dt_orig)
        
        # Hay casos donde npts reportado en header diffiere de actual size
        min_len = min(len(time_orig), len(accel_orig))
        time_orig = time_orig[:min_len]
        accel_orig = accel_orig[:min_len]

        # Vector de tiempo objetivo (target)
        duration = time_orig[-1]
        time_target = np.arange(0, duration, self.target_dt)

        # Interpolación (Normalización temporal)
        interpolator = interp1d(time_orig, accel_orig, kind='linear', fill_value="extrapolate")
        accel_resampled = interpolator(time_target)

        print(f"⚖️  [NYQUIST] Remuestreo: {dt_orig}s ({1/dt_orig:.1f}Hz) -> {self.target_dt}s ({self.target_freq}Hz)")
        print(f"⚖️  [NYQUIST] Puntos ajustados: {len(accel_orig)} -> {len(accel_resampled)}")

        return accel_resampled

if __name__ == "__main__":
    # Test rápido de sintaxis
    print("Módulo PEER Adapter operativo para Belico Stack.")
