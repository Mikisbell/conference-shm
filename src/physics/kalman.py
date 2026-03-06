"""
src/physics/kalman.py — Shadow Play (Filtro de Kalman 1D)
=========================================================
Implementa un Filtro de Kalman unidimensional en tiempo real para separar 
el ruido electrónico del sensor de Arduino de la demanda estructural real.

Por qué es necesario en el Stack Bélico:
Si un sensor lanza un pico falso de aceleración por ruido electromagnético,
el Protocolo de Aborto podría disparar un falso positivo (RL-2 Esfuerzo Crítico).
El Filtro de Kalman actúa como "Shadow Play": estima el estado verdadero 
basándose en ruido estadísticamente esperado (Q y R en params.yaml).
"""

class RealTimeKalmanFilter1D:
    def __init__(self, q: float, r: float, initial_state: float = 0.0, initial_estimate_error: float = 1.0):
        """
        :param q: Varianza del ruido del proceso (Q). Confianza en la física.
        :param r: Varianza del ruido de medición (R). Confianza en el sensor (Arduino).
        """
        self.q = q
        self.r = r
        
        # Estado inicial
        self.x_est = initial_state
        self.p_est = initial_estimate_error
        
        # Métrica SHM: Residuo de Innovación y su Varianza Teórica (S)
        self.innovation = 0.0
        self.s = 0.0

    def step(self, measurement: float) -> tuple[float, float, float]:
        """
        Ejecuta un paso de predicción y actualización.
        :param measurement: Lectura cruda del sensor.
        :return: (Estimación filtrada del estado, Residuo de Innovación, Varianza de la Innovación S)
        """
        # Predicción (modelo estático para aceleración, x_{k|k-1} = x_{k-1|k-1})
        x_pred = self.x_est
        p_pred = self.p_est + self.q

        # Cálculo de la Innovación (Métrica Predictiva SHM)
        self.innovation = measurement - x_pred
        self.s = p_pred + self.r

        # Actualización
        k_gain = p_pred / self.s  # Ganancia de Kalman
        self.x_est = x_pred + k_gain * self.innovation
        self.p_est = (1 - k_gain) * p_pred

        return self.x_est, self.innovation, self.s
