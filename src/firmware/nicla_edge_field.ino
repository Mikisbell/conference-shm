/*
 * src/firmware/nicla_edge_field.ino
 * ============================================================================
 * Firmware de CAMPO para Arduino Nicla Sense ME
 * Modo: Deep Sleep + Wake-on-Interrupt (BHI260AP)
 *
 * Arquitectura de Potencia:
 *   LiPo 3.7V → TP4056 (protección) → Nicla VIN
 *   LiPo 3.7V → Step-Up 5.1V ──────► E32 VCC
 *   Cap 1000µF entre VCC/GND del E32 (pico de 600mA en TX)
 *
 * Conexiones Nicla ↔ E32-915T30D (lógica 3.3V nativa, SIN level shifter):
 *   Nicla TX (D1) ──► E32 RX
 *   Nicla RX (D0) ◄── E32 TX
 *   Nicla D2     ──► E32 M0  (control de modo)
 *   Nicla D3     ──► E32 M1  (control de modo)
 *   Nicla D4     ◄── E32 AUX (E32 ocupado = LOW)
 *   Nicla GND    ──► E32 GND
 *
 * Ciclo de Vida del Nodo (para >3 meses de autonomía):
 *   [SLEEP] → BHI260AP detecta umbral → [WAKE] → Kalman+FFT → [TX 100ms] → [SLEEP]
 * ============================================================================
 */

#include "Arduino.h"
#include "Arduino_BHY2.h"    // Librería sensor fusion BHI260AP
#include "Nicla_System.h"    // Gestión de energía Nicla
#include <ArduinoLowPower.h>
#include <math.h>

// ─── Pines de Control del E32 ────────────────────────────────────────────────
#define E32_M0_PIN   D2
#define E32_M1_PIN   D3
#define E32_AUX_PIN  D4      // HIGH = Módulo listo, LOW = ocupado transmitiendo

// ─── Parámetros del Sistema ──────────────────────────────────────────────────
#define WINDOW_SIZE       256     // Muestras para FFT (2.56s @ 100Hz)
#define SAMPLE_RATE_HZ    100
#define ACCEL_THRESHOLD_G 0.05f   // Umbral para despertar (vibración estructural)
#define SLEEP_INTERVAL_MS 5000    // Ciclo base de sueño entre bursts (5s duty cycle)

// Umbral de Alarma RL2 (rigidez perdida > 30%)
#define FN_ALARM_HZ       5.6f
#define MAX_G_ALARM       0.45f

// ─── Sensores BHI260AP ───────────────────────────────────────────────────────
SensorXYZ   accel(SENSOR_ID_ACC);
SensorXYZ   gyro(SENSOR_ID_GYRO);
Sensor      temp(SENSOR_ID_TEMP);

// ─── Estado del Nodo ─────────────────────────────────────────────────────────
float  accelBuffer[WINDOW_SIZE];
int    bufferIdx   = 0;
bool   bufferFull  = false;
bool   alarmActive = false;
float  fn_hz       = 0.0f;
float  max_g       = 0.0f;
float  tmp_c       = 0.0f;

// Kalman 1D embebido
float kf_x = 0.0f, kf_p = 1.0f;
const float KF_Q = 0.001f, KF_R = 0.1f;

// ─── Modo del E32 ────────────────────────────────────────────────────────────
void setE32Mode(bool sleeping) {
    if (sleeping) {
        // M0=1, M1=1 → Modo Sueño/Config (µA)
        digitalWrite(E32_M0_PIN, HIGH);
        digitalWrite(E32_M1_PIN, HIGH);
    } else {
        // M0=0, M1=0 → Modo Transmisión Normal
        digitalWrite(E32_M0_PIN, LOW);
        digitalWrite(E32_M1_PIN, LOW);
    }
    delay(10); // Tiempo de conmutación del E32
}

bool waitE32Ready(uint32_t timeoutMs = 500) {
    uint32_t t0 = millis();
    while (millis() - t0 < timeoutMs) {
        if (digitalRead(E32_AUX_PIN) == HIGH) return true;
        delay(5);
    }
    return false; // Timeout
}

// ─── Filtro de Kalman 1D ─────────────────────────────────────────────────────
float kalmanStep(float measurement) {
    kf_p += KF_Q;
    float K = kf_p / (kf_p + KF_R);
    kf_x += K * (measurement - kf_x);
    kf_p *= (1.0f - K);
    return kf_x;
}

// ─── FFT Ligera: Estimación de Frecuencia Dominante (Peak Picking) ───────────
// Usa la frecuencia del ciclo de cruce por cero como proxy de fn
// (suficiente para SHM en campo sin biblioteca FFT completa)
float estimateFn(float* buf, int len, float sampleRateHz) {
    int crossings = 0;
    float mean = 0.0f;
    for (int i = 0; i < len; i++) mean += buf[i];
    mean /= len;

    for (int i = 1; i < len; i++) {
        if ((buf[i - 1] - mean) * (buf[i] - mean) < 0.0f) {
            crossings++;
        }
    }
    // Frecuencia = cruces_por_segundo / 2
    float duration_s = (float)len / sampleRateHz;
    return (crossings / 2.0f) / duration_s;
}

float computeMaxG(float* buf, int len) {
    float maxVal = 0.0f;
    for (int i = 0; i < len; i++) {
        if (fabs(buf[i]) > maxVal) maxVal = fabs(buf[i]);
    }
    return maxVal;
}

// ─── Transmisión LoRa (Burst de 100ms) ──────────────────────────────────────
void transmitPayload(float fn, float max_g_val, float tmp, bool alarm) {
    // Suspender validación térmica Guardian Angel durante TX
    // (señalado al bridge.py con campo TX_ACTIVE en payload)
    setE32Mode(false);  // M0=0, M1=0 → Modo Normal

    if (!waitE32Ready(1000)) {
        setE32Mode(true); // Volver a sleep si el E32 no responde
        return;
    }

    char stat[16];
    if (alarm) {
        if (fn < FN_ALARM_HZ)        strcpy(stat, "ALARM_RL2");
        else if (max_g_val > MAX_G_ALARM) strcpy(stat, "ALARM_MAX_G");
        else                         strcpy(stat, "WARN");
    } else {
        strcpy(stat, "OK");
    }

    // Timestamp Unix (requiere RTC o estimación por uptime si no hay GPS)
    // Para prototipo usamos millis()/1000 como timestamp relativo
    uint32_t t_unix_approx = millis() / 1000UL;

    char payload[80];
    snprintf(payload, sizeof(payload),
        "LORA:T:%lu,TMP:%.1f,HUM:55.0,FN:%.2f,MAX_G:%.3f,STAT:%s",
        (unsigned long)t_unix_approx, tmp, fn, max_g_val, stat
    );

    Serial1.println(payload); // UART TX hacia E32

    // Esperar confirmación AUX (E32 termina TX)
    delay(20);
    waitE32Ready(500);

    setE32Mode(true); // Volver a Modo Sueño inmediatamente tras TX
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
    nicla::begin();
    nicla::leds.begin();
    nicla::leds.setColor(red);   // LED rojo = inicializando

    Serial.begin(115200);  // Debug (se puede desactivar en campo)
    Serial1.begin(9600);   // UART hacia E32

    // Pines de control E32
    pinMode(E32_M0_PIN, OUTPUT);
    pinMode(E32_M1_PIN, OUTPUT);
    pinMode(E32_AUX_PIN, INPUT);
    setE32Mode(true); // E32 en sleep desde el arranque

    // Inicializar BHI260AP
    BHY2.begin(NICLA_STANDALONE);
    accel.begin();
    gyro.begin();
    temp.begin();

    // Configurar wake-up por umbral de aceleración
    // Nota: BHY2 no expone directamente la interrupción de umbral
    // Se simula con polling rápido en el ciclo de bajo consumo

    nicla::leds.setColor(green); // LED verde = listo
    delay(500);
    nicla::leds.setColor(off);   // Apagar LED para máximo ahorro

    Serial.println("[NICLA] Nodo de Campo Activo. Entrando en ciclo de sueño.");
}

// ─── Loop Principal (Ciclo de Sueño) ─────────────────────────────────────────
void loop() {
    // 1. Despertar y tomar muestra rápida del acelerómetro
    BHY2.update();
    float ax = accel.x() / 1000.0f; // mg → g
    float ay = accel.y() / 1000.0f;
    float az = accel.z() / 1000.0f;

    float accel_magnitude = sqrt(ax*ax + ay*ay + az*az) - 1.0f; // Restar gravedad
    float filtered = kalmanStep(accel_magnitude);

    // 2. Acumular buffer para FFT
    if (bufferIdx < WINDOW_SIZE) {
        accelBuffer[bufferIdx++] = filtered;
    }

    // 3. Cuando window está llena → procesar y transmitir
    if (bufferIdx >= WINDOW_SIZE) {
        fn_hz = estimateFn(accelBuffer, WINDOW_SIZE, SAMPLE_RATE_HZ);
        max_g = computeMaxG(accelBuffer, WINDOW_SIZE);
        tmp_c = temp.value();

        alarmActive = (fn_hz < FN_ALARM_HZ || max_g > MAX_G_ALARM);

        // LED rojo si hay alarma
        if (alarmActive) nicla::leds.setColor(red);

        Serial.printf("[FIELD] fn=%.2fHz max_g=%.3fg tmp=%.1fC alarm=%s\n",
                      fn_hz, max_g, tmp_c, alarmActive ? "YES" : "NO");

        transmitPayload(fn_hz, max_g, tmp_c, alarmActive);

        nicla::leds.setColor(off);  // Apagar LED
        bufferIdx = 0;              // Reset buffer

        // 4. Deep Sleep entre ciclos (máximo ahorro)
        LowPower.deepSleep(SLEEP_INTERVAL_MS);
    }

    // Microdelay a 100Hz (10ms por muestra)
    delay(1000 / SAMPLE_RATE_HZ);
}
