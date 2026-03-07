# AUTO-GENERATED — No editar manualmente.
# Fuente: config/params.yaml  |  Hash: bb8980cc6af0577e
# Regenerar: python3 tools/generate_params.py

CONFIG_HASH = "bb8980cc6af0577e4d5f42b6bc6b165b30c03a7d8860ff6dab2e4d0354fb833d"

# Material
MATERIAL_NAME = ""
E         = 20e9
fc        = 20e6
nu        = 0.2
rho       = 1800.0
k_term    = 0.51

# Estructura
k         = 5000.0
MASS_M    = 1000.0

# Damping
DAMPING_RATIO = 0.05

# Adquisición
BAUD_RATE = 115200
SAMPLE_RATE_HZ = 100

# Kalman
KF_ENABLED = True
KF_Q       = 1e-05
KF_R       = 0.01

# Temporal
DT         = 0.01
MAX_JITTER = 5
BUFFER_DEPTH = 10

# Nonlinear model status
NONLINEAR_READY = False
