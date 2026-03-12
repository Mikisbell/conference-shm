# AUTO-GENERATED — Do not edit manually.
# Source: config/params.yaml  |  Hash: a1da6a148023d551
# Regenerate: python3 tools/generate_params.py
# For runtime YAML access (always fresh), use src/physics/models/params.py instead.

CONFIG_HASH = "a1da6a148023d5512923dc14c53ff0a1e4e291e8f41771abcbe3dd70f7d112e3"

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

# Design (E.030)
DESIGN_Z  = 0.45

# Guardrails
MAX_STRESS_RATIO       = 0.6
CONVERGENCE_TOLERANCE  = 1e-06
MAX_SLENDERNESS        = 120
ECCENTRICITY_RATIO     = 0.1
MASS_PARTICIPATION_MIN = 0.9
MAX_SENSOR_SIGMA       = 3.0
ABORT_JITTER_MS        = 10.0
ABORT_JITTER_CONSEC    = 3
STRESS_RATIO_ABORT     = 0.85
LORA_STALE_TIMEOUT_S   = 15.0

# Nonlinear model status
NONLINEAR_READY = False
