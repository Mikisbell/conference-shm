/*
 * ═══════════════════════════════════════════════════════════════════
 * BELICO STACK — Firmware v1.0
 * Hardware: Arduino Nano 33 BLE Sense Rev2
 * ═══════════════════════════════════════════════════════════════════
 *
 * SENSORES INTEGRADOS ACTIVADOS:
 *   - BMI270      → Acelerómetro + Giroscopio (SHM / vibración estructural)
 *   - BME688      → Temperatura, Humedad, Presión, VOC (calidad del aire)
 *   - HS3003      → Temperatura + Humedad (redundancia de precisión)
 *   - PDM Mic     → Nivel sonoro RMS (emisión acústica / grietas)
 *
 * FORMATO DE SALIDA SERIAL (compatible con bridge.py):
 *   T:{millis},A:{accel_g},D:0.00,GX:{gx},GY:{gy},GZ:{gz},
 *   TMP:{temp_c},HUM:{hum_pct},PRS:{pres_hpa},VOC:{voc_ohm},
 *   SND:{sound_rms}\n
 *
 * PROTOCOLO HANDSHAKE (igual al del emulador):
 *   1. Esperar "HANDSHAKE:<token>:<hash>\n" desde bridge.py
 *   2. Responder "ACK_OK\n" si el token coincide
 *   3. Esperar "TIME_SYNC\n" → responder con "T:{millis},A:0.0,D:0.0\n"
 *   4. Iniciar bucle de transmisión a 100 Hz
 *
 * LIBRERÍAS REQUERIDAS (Arduino IDE → Library Manager):
 *   - Arduino_BMI270_BMM150  (IMU Rev2)
 *   - Arduino_BME68x         (gas / presión / temperatura)
 *   - Arduino_HS300x         (temperatura / humedad precisión)
 *   - PDM                    (micrófono — incluida en el core)
 *
 * INSTALACIÓN RAPIDA (Arduino CLI):
 *   arduino-cli lib install "Arduino_BMI270_BMM150"
 *   arduino-cli lib install "Arduino_BME68x"
 *   arduino-cli lib install "Arduino_HS300x"
 *
 * ═══════════════════════════════════════════════════════════════════
 */

#include <Arduino_BMI270_BMM150.h>
#include <Arduino_BME68x.h>
#include <Arduino_HS300x.h>
#include <PDM.h>

// ─── Configuración ────────────────────────────────────────────────
#define BAUD_RATE       115200
#define SAMPLE_RATE_HZ  100         // Hz — debe coincidir con params.yaml
#define DT_MS           (1000 / SAMPLE_RATE_HZ)
#define HANDSHAKE_TOKEN "BELICO_V1"  // Debe coincidir con params.yaml

// Buffer PDM (micrófono)
#define PDM_BUFFER_SIZE 256
short pdm_buffer[PDM_BUFFER_SIZE];
volatile bool pdm_ready = false;
float sound_rms = 0.0;

// Control de tiempo
unsigned long last_sample_ms = 0;

// ─── Callbacks PDM ────────────────────────────────────────────────
void onPDMdata() {
  int available = PDM.available();
  if (available > PDM_BUFFER_SIZE * 2) available = PDM_BUFFER_SIZE * 2;
  PDM.read(pdm_buffer, available);
  pdm_ready = true;
}

// ─── Calcular RMS del buffer de micrófono ─────────────────────────
float calcRMS() {
  long sum = 0;
  int n = PDM_BUFFER_SIZE;
  for (int i = 0; i < n; i++) sum += (long)pdm_buffer[i] * pdm_buffer[i];
  return sqrt((float)sum / n) / 32768.0f; // Normalizado 0.0–1.0
}

// ─── Setup ────────────────────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);
  while (!Serial);

  // IMU BMI270
  if (!IMU.begin()) {
    Serial.println("ERR:IMU_INIT_FAIL");
    while (true);
  }
  IMU.setAccelerationRange(16);  // ±16g para eventos sísmicos
  IMU.setGyroscopeRange(2000);   // ±2000 dps

  // BME688 (Aire)
  if (!BME68x.begin()) {
    Serial.println("WARN:BME688_ABSENT");  // No fatal — continúa sin él
  }

  // HS3003 (Temperatura/Humedad precisión)
  if (!HS300x.begin()) {
    Serial.println("WARN:HS3003_ABSENT");
  }

  // Micrófono PDM
  PDM.onReceive(onPDMdata);
  if (!PDM.begin(1, 16000)) {  // Mono, 16kHz
    Serial.println("WARN:PDM_ABSENT");
  }

  // ─── Protocolo de Handshake con bridge.py ──────────────────────
  // Esperar el token HANDSHAKE:<token>:<config_hash>
  bool handshake_ok = false;
  unsigned long hs_start = millis();

  while (!handshake_ok && (millis() - hs_start < 30000)) {
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      line.trim();
      if (line.startsWith("HANDSHAKE:")) {
        // Parsear token (posición 10 hasta el segundo ":")
        int sep = line.indexOf(':', 10);
        String token = (sep > 0) ? line.substring(10, sep) : line.substring(10);
        if (token == HANDSHAKE_TOKEN) {
          Serial.println("ACK_OK");
          handshake_ok = true;
        } else {
          Serial.println("ACK_FAIL_HASH");
        }
      }
    }
  }

  if (!handshake_ok) {
    // Timeout de handshake — operar en modo standalone (sin bridge)
    // Útil para debug con el Monitor Serial de Arduino IDE
    Serial.println("WARN:STANDALONE_MODE");
  }

  // Esperar TIME_SYNC
  hs_start = millis();
  while (millis() - hs_start < 5000) {
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      if (line.indexOf("TIME_SYNC") >= 0) {
        // Responder con timestamp + aceleración cero (calibración inicial)
        Serial.print("T:"); Serial.print(millis());
        Serial.println(",A:0.0,D:0.0");
        break;
      }
    }
  }

  last_sample_ms = millis();
}

// ─── Loop principal ───────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // Control de tasa de muestreo
  if (now - last_sample_ms < DT_MS) return;
  last_sample_ms = now;

  // ── 1. IMU: Aceleración + Giroscopio ──
  float ax = 0, ay = 0, az = 0;
  float gx = 0, gy = 0, gz = 0;

  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);
  }
  if (IMU.gyroscopeAvailable()) {
    IMU.readGyroscope(gx, gy, gz);
  }

  // Módulo de aceleración resultante (excluyendo gravedad en reposo)
  // En campo: el sensor se fija horizontal → az ≈ 1g en reposo
  // El bridge espera la componente de vibración:
  float accel_g = sqrt(ax*ax + ay*ay + az*az) - 1.0f;

  // ── 2. BME688: Aire (temperatura, humedad, presión, VOC) ──
  float temp_c   = 0, hum_pct = 0, pres_hpa = 0, voc_ohm = 0;
  if (BME68x.update()) {
    temp_c   = BME68x.temperature;
    hum_pct  = BME68x.humidity;
    pres_hpa = BME68x.pressure / 100.0f;  // Pa → hPa
    voc_ohm  = BME68x.gas_resistance;
  }

  // ── 3. HS3003: Temperatura/Humedad de alta precisión ──
  float tmp2 = 0, hum2 = 0;
  if (HS300x.update()) {
    tmp2 = HS300x.readTemperature();
    hum2 = HS300x.readHumidity();
    // Usar HS3003 como fuente primaria si BME no está disponible
    if (temp_c == 0) { temp_c = tmp2; hum_pct = hum2; }
  }

  // ── 4. Micrófono: Nivel sonoro (emisión acústica) ──
  if (pdm_ready) {
    sound_rms = calcRMS();
    pdm_ready = false;
  }

  // ── Verificar comandos entrantes (SHUTDOWN desde bridge.py) ──
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.indexOf("SHUTDOWN") >= 0) {
      // Detener transmisión — el bridge solicitó el cierre
      Serial.println("ACK_SHUTDOWN");
      while (true) { delay(1000); }  // Esperar reset manual
    }
  }

  // ── Emitir paquete de datos ──
  // Formato base (bridge.py): T:{ms},A:{g},D:0.00
  // Campos extendidos para Dashboard y Paper Maestro
  Serial.print("T:"); Serial.print(now);
  Serial.print(",A:"); Serial.print(accel_g, 4);
  Serial.print(",D:0.00");
  Serial.print(",GX:"); Serial.print(gx, 2);
  Serial.print(",GY:"); Serial.print(gy, 2);
  Serial.print(",GZ:"); Serial.print(gz, 2);
  Serial.print(",TMP:"); Serial.print(temp_c, 1);
  Serial.print(",HUM:"); Serial.print(hum_pct, 1);
  Serial.print(",PRS:"); Serial.print(pres_hpa, 1);
  Serial.print(",VOC:"); Serial.print(voc_ohm, 0);
  Serial.print(",SND:"); Serial.print(sound_rms, 4);
  Serial.println();
}
