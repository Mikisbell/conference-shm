"""
src/physics/torture_chamber.py — Torture Chamber (Dual Model: Linear / Nonlinear P-Delta)
=========================================================================================
Column model in OpenSeesPy with two modes:

  LINEAR (fallback):
    elasticBeamColumn + Elastic material.
    Used when nonlinear parameters in SSOT are null (factory mode / no project data).

  NONLINEAR (production):
    forceBeamColumn + Concrete02 + Steel02 + Fiber section.
    Activated when all required nonlinear parameters are populated in SSOT.
    Supports: cracking, crushing, yielding, cyclic degradation, P-Delta.

All parameters come from config/params.yaml (SSOT). Never hardcode values here.
"""

import math
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[TORTURE] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import openseespy.opensees as ops
except ImportError:
    print("[TORTURE] openseespy not installed. Run: pip install openseespy", file=sys.stderr)
    sys.exit(1)

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from config.paths import get_params_file
from src.physics.solver_backend import SolverBackend


def _load_ssot() -> dict:
    """Load the full raw SSOT dict from config/params.yaml.

    Returns the complete YAML tree (nonlinear, material, structure, damping, etc.)
    needed to build the fiber section and run nonlinear analysis.

    For the subset of scalar simulation params {mass, k, fy, xi, integrator},
    see the canonical loader: src/physics/models/params.load_sim_params().
    Both functions use config.paths.get_params_file() as the single source of truth
    for the YAML path — no hardcoded relative paths.

    # Params via canonical SSOT path — see config/paths.py → get_params_file()
    """
    params_path = get_params_file()
    try:
        with open(params_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"[TORTURE] ERROR: params.yaml not found at {params_path}"
              " — run: python3 tools/generate_params.py", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[TORTURE] ERROR: params.yaml malformed: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[TORTURE] ERROR: cannot read params.yaml: {e}", file=sys.stderr)
        sys.exit(1)


def _require(cfg: dict, dotpath: str):
    """Get a required SSOT value by dotpath — sys.exit(1) with diagnostics if absent.

    Uses _get_nested() to traverse the YAML tree and extract the terminal .value.
    Example: _require(cfg, "nonlinear.concrete.epsc0")
             → cfg["nonlinear"]["concrete"]["epsc0"]["value"]
    """
    val = _get_nested(cfg, dotpath)
    if val is None:
        print(f"[TORTURE] ERROR: SSOT missing required key '{dotpath}' "
              "in config/params.yaml", file=sys.stderr)
        sys.exit(1)
    return val


def _nonlinear_ready(cfg: dict) -> bool:
    """Check if all required nonlinear parameters are populated (non-null)."""
    nl = cfg.get("nonlinear")
    if nl is None:
        return False

    for section_key in ("concrete", "steel", "section", "geometry"):
        section = nl.get(section_key, {})
        for param_key, param in section.items():
            if isinstance(param, dict) and param.get("required", False):
                if param.get("value") is None:
                    return False
    return True


def _build_fiber_section(cfg: dict, sec_tag: int = 1):
    """Build a fiber section with confined/unconfined concrete and steel layers."""
    # Concrete properties
    fc         = float(_require(cfg, "material.yield_strength_fy"))  # fc' (compressive strength)
    epsc0      = float(_require(cfg, "nonlinear.concrete.epsc0"))
    fpcu_ratio = float(_require(cfg, "nonlinear.concrete.fpcu_ratio"))
    epsU       = float(_require(cfg, "nonlinear.concrete.epsU"))
    ft_ratio   = float(_require(cfg, "nonlinear.concrete.ft_ratio"))
    Ets        = float(_require(cfg, "nonlinear.concrete.Ets"))
    conf_ratio = float(_require(cfg, "nonlinear.concrete.confinement_ratio"))

    # Steel properties
    fy_steel = float(_require(cfg, "nonlinear.steel.fy"))
    Es_steel = float(_require(cfg, "nonlinear.steel.Es"))
    b_hard   = float(_require(cfg, "nonlinear.steel.b_hardening"))
    R0       = float(_require(cfg, "nonlinear.steel.R0"))
    cR1      = float(_require(cfg, "nonlinear.steel.cR1"))
    cR2      = float(_require(cfg, "nonlinear.steel.cR2"))

    # Section geometry
    b       = float(_require(cfg, "nonlinear.geometry.b"))
    cover   = float(_require(cfg, "nonlinear.section.cover"))
    n_bars  = int(_require(cfg, "nonlinear.section.n_bars_face"))
    bar_dia = float(_require(cfg, "nonlinear.section.bar_diameter"))
    bar_area = math.pi * (bar_dia / 2.0) ** 2

    # Fiber discretization — from SSOT if present, else documented defaults
    n_fiber_core  = int(_get_nested(cfg, "nonlinear.section.n_fiber_core")  or 10)
    n_fiber_cover = int(_get_nested(cfg, "nonlinear.section.n_fiber_cover") or 2)

    # Derived
    fpc_conf = fc * conf_ratio
    epsc0_conf = epsc0 * conf_ratio  # Mander approximation
    fpcu_conf = fpcu_ratio * fpc_conf
    epsU_conf = epsU * conf_ratio
    ft = ft_ratio * fc
    fpcu_unconf = fpcu_ratio * fc

    # Material tags
    MAT_CONF = 10    # Confined concrete (core)
    MAT_UNCONF = 20  # Unconfined concrete (cover)
    MAT_STEEL = 30   # Reinforcing steel

    # Concrete02: confined core
    # Concrete02(matTag, fpc, epsc0, fpcu, epsU, lambda, ft, Ets)
    ops.uniaxialMaterial('Concrete02', MAT_CONF,
                         -fpc_conf, -epsc0_conf, -fpcu_conf, -epsU_conf,
                         0.1, ft, Ets)

    # Concrete02: unconfined cover
    ops.uniaxialMaterial('Concrete02', MAT_UNCONF,
                         -fc, -epsc0, -fpcu_unconf, -epsU,
                         0.1, ft, Ets)

    # Steel02: reinforcing bars
    ops.uniaxialMaterial('Steel02', MAT_STEEL,
                         fy_steel, Es_steel, b_hard, R0, cR1, cR2)

    # Fiber section
    core_b = b - 2.0 * cover  # core dimension
    half_b = b / 2.0
    half_core = core_b / 2.0

    ops.section('Fiber', sec_tag)

    # Core concrete (confined) — rectangular patch
    n_fiber_core = 10  # fibers in each direction
    ops.patch('rect', MAT_CONF, n_fiber_core, n_fiber_core,
              -half_core, -half_core, half_core, half_core)

    # Cover concrete (unconfined) — 4 patches around core
    n_fiber_cover = 2
    # Bottom cover
    ops.patch('rect', MAT_UNCONF, n_fiber_cover, n_fiber_core,
              -half_b, -half_b, half_b, -half_core)
    # Top cover
    ops.patch('rect', MAT_UNCONF, n_fiber_cover, n_fiber_core,
              -half_b, half_core, half_b, half_b)
    # Left cover
    ops.patch('rect', MAT_UNCONF, n_fiber_core, n_fiber_cover,
              -half_b, -half_core, -half_core, half_core)
    # Right cover
    ops.patch('rect', MAT_UNCONF, n_fiber_core, n_fiber_cover,
              half_core, -half_core, half_b, half_core)

    # Steel layers — top and bottom faces
    y_steel = half_core  # steel placed at core boundary
    ops.layer('straight', MAT_STEEL, n_bars, bar_area,
              -y_steel, -y_steel, -y_steel, y_steel)  # bottom
    ops.layer('straight', MAT_STEEL, n_bars, bar_area,
              y_steel, -y_steel, y_steel, y_steel)     # top

    print(f"[OPENSEES]   Fiber section built: core={core_b:.3f}m, "
          f"fc_conf={fpc_conf/1e6:.1f}MPa, fy_steel={fy_steel/1e6:.0f}MPa, "
          f"{2*n_bars} bars dia={bar_dia*1000:.0f}mm")

    return {
        "MAT_CONF": MAT_CONF,
        "MAT_UNCONF": MAT_UNCONF,
        "MAT_STEEL": MAT_STEEL,
        "sec_tag": sec_tag,
    }


def init_model() -> dict:
    """Initialize the Torture Chamber from SSOT parameters.

    Returns a dict with computed model properties for use by bridge.py.
    Automatically selects linear or nonlinear model based on SSOT completeness.
    """
    cfg = _load_ssot()
    use_nonlinear = _nonlinear_ready(cfg)

    # Material from SSOT
    E   = float(_require(cfg, "material.elastic_modulus_E"))
    fy  = float(_require(cfg, "material.yield_strength_fy"))
    rho = float(_require(cfg, "material.density"))

    # Structure from SSOT
    m = float(_require(cfg, "structure.mass_m"))
    k = float(_require(cfg, "structure.stiffness_k"))

    # Damping from SSOT
    xi = float(_require(cfg, "damping.ratio_xi"))

    mode = "NONLINEAR (Concrete02+Steel02+Fiber)" if use_nonlinear else "LINEAR (elastic fallback)"
    print(f"[OPENSEES] Torture Chamber — {mode}")
    print(f"[OPENSEES]   E={E/1e9:.1f}GPa  fc={fy/1e6:.1f}MPa  rho={rho:.0f}kg/m3")
    print(f"[OPENSEES]   m={m:.0f}kg  k={k:.0f}N/m  xi={xi:.1%}")

    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 3)

    if use_nonlinear:
        return _init_nonlinear(cfg, E, fy, rho, m, k, xi)
    else:
        return _init_linear(cfg, E, fy, rho, m, k, xi)


def _init_linear(cfg: dict, E: float, fy: float, rho: float,
                 m: float, k: float, xi: float) -> dict:
    """Linear elastic model (factory fallback — no project data yet)."""
    # Geometry — try SSOT first (nonlinear.geometry); fall back to factory defaults
    _L_ssot = _get_nested(cfg, "nonlinear.geometry.L")
    _b_ssot = _get_nested(cfg, "nonlinear.geometry.b")
    if _L_ssot is not None and _b_ssot is not None:
        L = float(_L_ssot)
        b = float(_b_ssot)
    else:
        L = 3.0   # factory default — add nonlinear.geometry.L to params.yaml
        b = 0.25  # factory default — add nonlinear.geometry.b to params.yaml
        print("[TORTURE] WARNING: Using factory geometry defaults L=3.0m b=0.25m"
              " — set nonlinear.geometry.L/b in params.yaml for project geometry",
              file=sys.stderr)
    A = b * b
    I = b**4 / 12.0

    print(f"[OPENSEES]   L={L:.1f}m  b={b:.2f}m  A={A:.4f}m2  I={I:.6e}m4")

    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, L)
    ops.fix(1, 1, 1, 1)

    ops.geomTransf('PDelta', 1)
    ops.uniaxialMaterial('Elastic', 1, E)
    ops.element('elasticBeamColumn', 1, 1, 2, A, E, I, 1)

    ops.mass(2, m, m, 0.0)

    # Axial load near Pcr (cantilever K=2: Pcr = pi^2*E*I / (4*L^2))
    Pcr = math.pi**2 * E * I / (4.0 * L**2)
    P_applied = -0.90 * Pcr
    print(f"[OPENSEES]   Pcr={Pcr:.0f}N  P_applied={abs(P_applied):.0f}N (90% Pcr)")

    ops.timeSeries('Constant', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(2, 0.0, P_applied, 0.0)

    # Static gravity
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-8, 10)
    ops.algorithm('Newton')
    ops.integrator('LoadControl', 1.0)
    ops.analysis('Static')
    ops.analyze(1)

    ops.loadConst('-time', 0.0)

    # Dynamic setup
    ops.timeSeries('Linear', 2)
    ops.pattern('Plain', 2, 2)

    # Rayleigh damping — mass-proportional only (linear model)
    wn = math.sqrt(k / m)
    a0 = xi * 2.0 * wn
    ops.rayleigh(a0, 0.0, 0.0, 0.0)

    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-6, 20)
    ops.algorithm('Newton')
    ops.integrator('Newmark', 0.5, 0.25)
    ops.analysis('Transient')

    print(f"[OPENSEES] Linear model ready. wn={wn:.2f}rad/s  fn={wn/(2*math.pi):.2f}Hz")

    return {
        "mass_kg": m,
        "E_pa": E,
        "fy_pa": fy,
        "I_m4": I,
        "A_m2": A,
        "L_m": L,
        "b_m": b,
        "xi": xi,
        "Pcr_N": Pcr,
        "wn_rad": wn,
        "nonlinear": False,
        "n_elements": 1,
        "top_node": 2,
    }


def _init_nonlinear(cfg: dict, E: float, fy: float, rho: float,
                    m: float, k: float, xi: float) -> dict:
    """Nonlinear fiber model with Concrete02 + Steel02 + P-Delta."""
    # Geometry from SSOT
    L      = float(_require(cfg, "nonlinear.geometry.L"))
    b      = float(_require(cfg, "nonlinear.geometry.b"))
    n_elem = int(_require(cfg, "nonlinear.geometry.n_elements"))
    n_ip   = int(_require(cfg, "nonlinear.section.n_integration_pts"))
    A = b * b
    I = b**4 / 12.0

    print(f"[OPENSEES]   L={L:.1f}m  b={b:.2f}m  n_elem={n_elem}  n_ip={n_ip}")

    # Nodes along column height
    for i in range(n_elem + 1):
        node_tag = i + 1
        y_coord = i * L / n_elem
        ops.node(node_tag, 0.0, y_coord)

    # Fix base
    ops.fix(1, 1, 1, 1)

    # Geometric transformation
    ops.geomTransf('PDelta', 1)

    # Build fiber section
    sec_info = _build_fiber_section(cfg, sec_tag=1)

    # Force-based beam-column elements with fiber section
    for i in range(n_elem):
        elem_tag = i + 1
        node_i = i + 1
        node_j = i + 2
        ops.beamIntegration('Lobatto', elem_tag, sec_info["sec_tag"], n_ip)
        ops.element('forceBeamColumn', elem_tag, node_i, node_j, 1, elem_tag)

    # Mass at top node
    top_node = n_elem + 1
    ops.mass(top_node, m, m, 0.0)

    # Axial load (gravity): self-weight + applied
    Pcr = math.pi**2 * E * I / (4.0 * L**2)
    P_applied = -0.90 * Pcr
    print(f"[OPENSEES]   Pcr={Pcr:.0f}N  P_applied={abs(P_applied):.0f}N (90% Pcr)")

    ops.timeSeries('Constant', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(top_node, 0.0, P_applied, 0.0)

    # Static gravity analysis
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-6, 50)
    ops.algorithm('Newton')
    ops.integrator('LoadControl', 0.1)  # 10 increments for nonlinear
    ops.analysis('Static')
    ops.analyze(10)

    ops.loadConst('-time', 0.0)

    # Rayleigh damping — mass + committed-stiffness proportional
    wn = math.sqrt(k / m)
    # For multi-mode: use w1 and w2 (assume w2 ~ 3*w1 for cantilever)
    w1 = wn
    w2 = 3.0 * wn  # 2nd mode approximation for cantilever
    a0 = xi * 2.0 * w1 * w2 / (w1 + w2)
    a1 = xi * 2.0 / (w1 + w2)
    ops.rayleigh(a0, 0.0, a1, 0.0)
    print(f"[OPENSEES]   Rayleigh: a0={a0:.4f} (mass), a1={a1:.6f} (stiffness)")

    # Dynamic analysis setup
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-6, 30)
    ops.algorithm('Newton')

    beta  = float(_require(cfg, "nonlinear.analysis.beta"))
    gamma = float(_require(cfg, "nonlinear.analysis.gamma"))
    ops.integrator('Newmark', gamma, beta)
    ops.analysis('Transient')

    print(f"[OPENSEES] Nonlinear model ready. wn={wn:.2f}rad/s  fn={wn/(2*math.pi):.2f}Hz")

    return {
        "mass_kg": m,
        "E_pa": E,
        "fy_pa": fy,
        "I_m4": I,
        "A_m2": A,
        "L_m": L,
        "b_m": b,
        "xi": xi,
        "Pcr_N": Pcr,
        "wn_rad": wn,
        "nonlinear": True,
        "n_elements": n_elem,
        "top_node": top_node,
    }


# ─────────────────────────────────────────────────────────
# SolverBackend implementation for bridge.py multi-domain
# ─────────────────────────────────────────────────────────

STRUCTURAL_REQUIRED_PARAMS = {
    "nonlinear.concrete.epsc0": "Deformacion al pico (typ. 0.002)",
    "nonlinear.concrete.fpcu_ratio": "Resistencia residual post-pico (typ. 0.2)",
    "nonlinear.concrete.epsU": "Deformacion ultima aplastamiento (typ. 0.005-0.008)",
    "nonlinear.concrete.ft_ratio": "Resistencia traccion / fc (typ. 0.08-0.12)",
    "nonlinear.concrete.Ets": "Pendiente tension stiffening (Pa)",
    "nonlinear.concrete.confinement_ratio": "Factor confinamiento fcc/fc (typ. 1.2-1.5)",
    "nonlinear.steel.fy": "Fluencia del acero (typ. 420e6 Pa Grado 60)",
    "nonlinear.steel.Es": "Modulo elastico acero (typ. 200e9 Pa)",
    "nonlinear.steel.b_hardening": "Ratio endurecimiento (typ. 0.01)",
    "nonlinear.section.cover": "Recubrimiento de concreto (m)",
    "nonlinear.section.n_bars_face": "Barras por cara",
    "nonlinear.section.bar_diameter": "Diametro de barra (m)",
    "nonlinear.section.stirrup_diameter": "Diametro del estribo (m)",
    "nonlinear.section.stirrup_spacing": "Separacion de estribos (m)",
    "nonlinear.geometry.L": "Longitud de columna (m)",
    "nonlinear.geometry.b": "Ancho de seccion cuadrada (m)",
}


def _get_nested(cfg: dict, dotpath: str):
    keys = dotpath.split(".")
    current = cfg
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if isinstance(current, dict):
        return current.get("value")
    return current


class StructuralBackend(SolverBackend):
    """OpenSeesPy solver for structural domain (seismic, P-Delta, SHM)."""

    @property
    def domain(self) -> str:
        return "structural"

    def init_model(self, cfg: dict) -> dict:
        return init_model()

    def step(self, measurement: float, dt: float, model_props: dict) -> dict:
        top_node = model_props.get("top_node", 2)
        mass_kg = model_props.get("mass_kg", 1000.0)
        I_m4 = model_props.get("I_m4", 0.25**4 / 12.0)
        b_m = model_props.get("b_m", 0.25)
        c = b_m / 2.0

        force = mass_kg * measurement * 9.81  # N (measurement = accel_g)
        ops.load(top_node, force, 0.0, 0.0)
        ok = ops.analyze(1, dt)

        try:
            ops.reactions()
            Mz_base = abs(ops.nodeReaction(1, 3))
            stress_pa = (Mz_base * c) / I_m4
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as _e:
            print(f"[TORTURE] WARNING: stress computation failed: {_e}"
                  " — stress_pa=0.0 (Guardian Angel RL-2 may not trigger)",
                  file=sys.stderr)
            stress_pa = 0.0

        return {
            "converged": ok == 0,
            "stress_pa": stress_pa,
        }

    def check_required_params(self, cfg: dict) -> list[tuple[str, str]]:
        missing = []
        for dotpath, desc in STRUCTURAL_REQUIRED_PARAMS.items():
            if _get_nested(cfg, dotpath) is None:
                missing.append((dotpath, desc))
        return missing
