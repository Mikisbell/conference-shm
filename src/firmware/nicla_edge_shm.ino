/*
 * src/firmware/nicla_edge_shm.ino
 * ============================================================================
 * Firmware BÉLICO EDGE AI para Arduino Nicla Sense ME
 * 
 * Actúa como un nodo IoT de procesamiento pesado en el borde.
 * En lugar de enviar aceleración en bruto a 100Hz (lo cual saturaría LoRa),
 * este microcontrolador maestrea internamente a 100Hz, limpia la señal con  
 * un Filtro de Kalman 1D, y acumula "ventanas" de 256 muestras (2.56 segs).
 * 
 * Luego ejecuta una Transformada Rápida de Fourier (FFT) On-Board
 * y emite UN SOLO PAQUETE con los resultados finales (Frecuencia Dominante, 
 * Aceleración Peak y Estado) hacia el módulo LoRa UART.
 * 
 * Dependencias de Librería Opcionales a instalar en Arduino IDE:
 *  - Arduino_BHY2 (Para sensores BHI260AP del Nicla Sense ME)
 *  - arduinoFFT (v1.x o v2.x)
 * ============================================================================
 */

#include "Arduino.h"
#include "Arduino_BHY2.h"
// #include "arduinoFFT.h" // Descomentar en IDE tras instalar arduinoFFT

// ─────────────────────────────────────────────────────────
// CONFIGURACIÓN DE SHM Y FÍSICA
// ─────────────────────────────────────────────────────────
#define SAMPLES 256            // Debe ser potencia de 2 para la FFT
#define SAMPLING_FREQ 100.0    // Hz
#define LORA_BAUD 9600         // Baudrate estándar para módulos LoRa UART (E32/E220)

// Umbrales de Seguridad (Red Lines Locales)
const float NOMINAL_FN = 8.0;  // Frecuencia estructural nominal (Hz)
const float FN_DROP_WARN = 0.90; // Caída del 10% -> WARN
const float FN_DROP_CRIT = 0.70; // Caída del 30% -> ALARM_RL2
const float MAX_G_CRIT   = 0.40; // Aceleración de alarma

// ─────────────────────────────────────────────────────────
// FILTRO DE KALMAN 1D P-DELTA (Edge AI)
// ─────────────────────────────────────────────────────────
class KalmanFilter1D {
private:
    float _q; // Process noise covariance
    float _r; // Measurement noise covariance
    float _p; // Estimation error covariance
    float _x; // State estimate

public:
    KalmanFilter1D(float q, float r, float p, float initial_value) {
        _q = q;
        _r = r;
        _p = p;
        _x = initial_value;
    }

    float step(float measurement) {
        // Predicción
        _p = _p + _q;
        
        // Actualización (Kalman Gain)
        float k = _p / (_p + _r);
        _x = _x + k * (measurement - _x);
        
        // Innovación (z - x) implícita en la ganancia
        _p = (1.0f - k) * _p;
        
        return _x;
    }
};

// Instancia del filtro (Q y R alineados con los de params.yaml)
KalmanFilter1D kf(1e-5, 0.01, 1.0, 0.0);

// ─────────────────────────────────────────────────────────
// MEMORIA Y FFT
// ─────────────────────────────────────────────────────────
SensorXYZ accel(SENSOR_ID_ACC);
Sensor temp(SENSOR_ID_TEMP);
Sensor hum(SENSOR_ID_HUM);

double vReal[SAMPLES];
double vImag[SAMPLES];
// arduinoFFT FFT = arduinoFFT(vReal, vImag, SAMPLES, SAMPLING_FREQ);

unsigned int sampleIndex = 0;
unsigned long sampling_period_us;
unsigned long microseconds;
float max_g_window = 0.0;

// Reloj Unix simulado (A ser ajustado por downlink si hay gateway)
unsigned long current_unix_epoch = 1710000000; 

// ─────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);   // Consola Debug (USB)
    Serial1.begin(LORA_BAUD); // Telemetría LoRa (Tx/Rx)

    while (!Serial && millis() < 3000); // Espera opcional a la consola serial
    
    Serial.println("=========================================");
    Serial.println("[NICLA EDGE AI] Iniciando Motor BHI260AP...");
    
    // Inicializar el Fuser Core del Nicla
    BHY2.begin();
    accel.begin(SAMPLING_FREQ, 0); // 100Hz
    temp.begin();
    hum.begin();

    sampling_period_us = round(1000000.0 / SAMPLING_FREQ);
    
    Serial.println("[NICLA EDGE AI] Sensores Activos.");
    Serial.println("[NICLA EDGE AI] Capturando vectores base...");
    Serial.println("=========================================");
}

// ─────────────────────────────────────────────────────────
// LOOP PRINCIPAL
// ─────────────────────────────────────────────────────────
void loop() {
    // 1. Muestreo de estricto tiempo real
    microseconds = micros();
    
    // Actualiza datos de los sensores desde el BHI260AP Fuser Core
    BHY2.update();

    // 2. Extraer, Filtrar y Almacenar
    // Nicla reporta en "g" multiplicados por 4096 o un vector directo.
    // Usamos el vector X como eje fuerte.
    float raw_g = accel.x() / 4096.0; // Normalización típica BHI
    
    // Someter la lectura cruda a la purga de Kalman
    float clean_g = kf.step(raw_g);

    // Detección de peak (para la amplitud máxima de la ventana)
    if (abs(clean_g) > max_g_window) {
        max_g_window = abs(clean_g);
    }

    // Guardar para el análisis espectral
    vReal[sampleIndex] = clean_g;
    vImag[sampleIndex] = 0.0;
    
    sampleIndex++;

    // 3. Cuando la ventana está llena, ejecutar Edge AI
    if (sampleIndex >= SAMPLES) {
        /*
        // EJECUCIÓN DE LA FFT EN SILICIO (Descomentar con la librería)
        FFT.Windowing(FFT_WIN_TYP_HANN, FFT_FORWARD);
        FFT.Compute(FFT_FORWARD);
        FFT.ComplexToMagnitude();
        double peak_freq = FFT.MajorPeak();
        */
        
        // (Mock de la salida de FFT mientras arduinoFFT no esté linkeado en el build)
        // Sustituiremos peak_freq con un dummy para validar la compilación y lógica.
        double peak_freq = NOMINAL_FN; 
        
        // Lógica de Estado Estructural
        String stat = "OK";
        if (peak_freq < (NOMINAL_FN * FN_DROP_CRIT) || max_g_window > MAX_G_CRIT) {
            stat = "ALARM_RL2";
        } else if (peak_freq < (NOMINAL_FN * FN_DROP_WARN)) {
            stat = "WARN";
        }

        // Simulación de reloj RTC (Sumamos 2.56 segs por ventana)
        current_unix_epoch += (SAMPLES / SAMPLING_FREQ);

        // 4. Empaquetar el "Resumen Ejecutivo" para el canal angosto de LoRa
        // Formato esperado por el Watchdog Telemétrico del bridge.py
        float t_val = temp.value();
        float h_val = hum.value();
        
        char payload[128];
        snprintf(payload, sizeof(payload), 
          "LORA:T:%lu,TMP:%.1f,HUM:%.1f,FN:%.2f,MAX_G:%.3f,STAT:%s\n",
          current_unix_epoch, t_val, h_val, peak_freq, max_g_window, stat.c_str()
        );

        // 5. Emitir al Espacio (Transmisor Tx Serial1 hacia módulo LoRa)
        Serial1.print(payload);
        
        // Debug local en Base
        Serial.print("[EDGE EVENT] ");
        Serial.print(payload);

        // Reset de la ventana
        sampleIndex = 0;
        max_g_window = 0.0;
    }

    // Spin-lock para mantener los 100 Hz precisos
    while(micros() < (microseconds + sampling_period_us)) {
        // Yield para evitar freezing
    }
}
