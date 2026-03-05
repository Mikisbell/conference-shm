# AUTO-GENERATED — No editar manualmente.
# Fuente: config/params.yaml  |  Hash: 3dd726ee4864d752
# Regenerar: python3 tools/generate_params.py

CONFIG_HASH = "3dd726ee4864d752023f29f4150bc58b4e8cef951b845bb1038f2ad1fade6272"

# Material
MATERIAL_NAME = "Concreto Liviano Reciclado C&DW"
E         = 20e9
fc        = 20e6
nu        = 0.2
rho       = 1800.0
k_term    = 0.51

# Estructura
k         = 5000.0

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
