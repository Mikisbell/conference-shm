// AUTO-GENERATED — No editar manualmente.
// Fuente: config/params.yaml  |  Hash: a1da6a148023d551
// Regenerar: python3 tools/generate_params.py
#pragma once

#define CONFIG_HASH     "a1da6a148023d551"

// ── Material ──
#define MATERIAL_NAME   ""
#define E_MODULUS       20e9
#define YIELD_STRENGTH  20e6
#define RHO             1800.0
#define K_TERM          0.51

// ── Structure ──
#define STIFFNESS_K     5000.0
#define MASS_M          1000.0

// ── Damping ──
#define DAMPING_RATIO   0.05

// ── Acquisition ──
#define SERIAL_BAUD     115200
#define SAMPLE_RATE_HZ  100

// ── Kalman Filter ──
#define KF_Q            1e-05
#define KF_R            0.01

// ── Temporal Sync ──
#define HANDSHAKE_TOKEN "BELICO_SYNC_2026"
#define MAX_JITTER_MS   5

// ── Guardrails ──
#define MAX_STRESS_RATIO  0.6
#define MAX_SENSOR_SIGMA  3.0

// ── Firmware Edge Common ──
#define WINDOW_SIZE_SAMPLES  256
#define ACCEL_THRESHOLD_G    0.05f
#define SLEEP_INTERVAL_MS    5000
#define LORA_BAUD            9600

// ── Firmware Edge Alarms ──
#define NOMINAL_FN_HZ        0.0f  // TODO: set after field calibration
#define FN_DROP_WARN_RATIO   0.9f
#define FN_DROP_CRIT_RATIO   0.7f
#define MAX_G_ALARM          0.4f

// ── Guardian Angel Gates ──
#define GA_RIGIDEZ_TOL_HZ    1.0
#define GA_RIGIDEZ_EXT_HZ    3.0
#define GA_TEMP_MIN_C         -5.0
#define GA_TEMP_MAX_C         80.0
#define GA_TEMP_EXT_MIN_C     -15.0
#define GA_TEMP_EXT_MAX_C     120.0
#define GA_GRAD_EXT_C         20.0
#define GA_GRAD_IMP_C         50.0
#define GA_BAT_UNRELIABLE_V   3.5
#define GA_BAT_CRITICAL_V     3.3
