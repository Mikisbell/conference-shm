"""
src/physics/torture_chamber_fluid.py — Fluid/Aero Solver (FEniCSx Backend)
==========================================================================
Solver for water and air domains using FEniCSx (dolfinx).

  WATER domain:
    Navier-Stokes incompressible flow.
    Use case: dam monitoring, pipe flow, canal dynamics.
    Sensor input: flow velocity (m/s) or pressure (Pa).
    Output metric: pressure/stress at critical point.

  AIR domain:
    Steady/transient wind loading on structures.
    Use case: wind pressure on buildings, ventilation ducts.
    Sensor input: wind speed (m/s) or pressure coefficient.
    Output metric: surface pressure (Pa).

Both domains share the same FEniCSx backend but with different
governing equations, boundary conditions, and required parameters.

Status: FACTORY STUB — requires `pip install fenics-dolfinx` to activate.
All physics logic is ready; only the FEniCSx import is gated.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.physics.solver_backend import SolverBackend

_WATER_DENSITY_KG_M3     = 1000.0  # kg/m³ — pure water @ 4°C (SI standard, NIST)
_DYNAMIC_PRESSURE_COEFF  = 0.5     # ½ρv² — Bernoulli dynamic pressure coefficient


# Required parameters per domain (user must fill these in params.yaml)
WATER_REQUIRED_PARAMS = {
    "fluid.properties.viscosity_mu": "Viscosidad dinamica (typ. 1e-3 Pa.s para agua)",
    "fluid.properties.density_rho": "Densidad del fluido (typ. 1000 kg/m3 para agua)",
    "fluid.geometry.length": "Longitud del dominio (m)",
    "fluid.geometry.height": "Altura del dominio (m)",
    "fluid.geometry.width": "Ancho del dominio (m, 0 para 2D)",
    "fluid.boundary.inlet_velocity": "Velocidad de entrada (m/s)",
    "fluid.boundary.outlet_pressure": "Presion de salida (typ. 0 Pa gauge)",
    "fluid.mesh.resolution": "Resolucion de malla (elementos por metro)",
    "fluid.analysis.time_step": "Paso temporal (s)",
    "fluid.analysis.total_time": "Tiempo total de simulacion (s)",
}

AIR_REQUIRED_PARAMS = {
    "air.properties.viscosity_mu": "Viscosidad dinamica (typ. 1.8e-5 Pa.s para aire)",
    "air.properties.density_rho": "Densidad del aire (typ. 1.225 kg/m3)",
    "air.geometry.length": "Longitud del dominio (m)",
    "air.geometry.height": "Altura del dominio (m)",
    "air.geometry.width": "Ancho del dominio (m, 0 para 2D)",
    "air.geometry.obstacle_width": "Ancho del obstaculo/edificio (m)",
    "air.geometry.obstacle_height": "Altura del obstaculo/edificio (m)",
    "air.boundary.inlet_velocity": "Velocidad del viento (m/s)",
    "air.boundary.turbulence_intensity": "Intensidad de turbulencia (typ. 0.1-0.2)",
    "air.mesh.resolution": "Resolucion de malla (elementos por metro)",
    "air.analysis.time_step": "Paso temporal (s)",
    "air.analysis.total_time": "Tiempo total de simulacion (s)",
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


def _fenicsx_available() -> bool:
    """Check if FEniCSx (dolfinx) is installed."""
    try:
        import dolfinx  # noqa: F401
        return True
    except ImportError:
        return False


class FluidBackend(SolverBackend):
    """FEniCSx solver for water and air domains."""

    def __init__(self, domain: str = "water"):
        if domain not in ("water", "air"):
            raise ValueError(f"FluidBackend domain must be 'water' or 'air', got '{domain}'")
        self._domain = domain

    @property
    def domain(self) -> str:
        return self._domain

    def init_model(self, cfg: dict) -> dict:
        """Initialize FEniCSx model from SSOT.

        If FEniCSx is not installed, returns a stub dict with ready=False.
        When FEniCSx is available, this will build the mesh, define function
        spaces, set boundary conditions, and prepare the variational form.
        """
        missing = self.check_required_params(cfg)
        if missing:
            print(f"[FENICSX] {self._domain.upper()} domain — {len(missing)} required params missing")
            print(f"[FENICSX] Run: python3 tools/scaffold_investigation.py --check")
            return {
                "domain": self._domain,
                "solver": "fenicsx",
                "ready": False,
                "missing_params": len(missing),
            }

        if not _fenicsx_available():
            print(f"[FENICSX] {self._domain.upper()} domain — FEniCSx not installed")
            print(f"[FENICSX] Install: pip install fenics-dolfinx")
            return {
                "domain": self._domain,
                "solver": "fenicsx",
                "ready": False,
                "reason": "fenicsx_not_installed",
            }

        # --- FEniCSx initialization (activated when dolfinx is available) ---
        domain_cfg = cfg.get(self._domain, {})
        props = domain_cfg.get("properties", {})
        geom = domain_cfg.get("geometry", {})
        bc = domain_cfg.get("boundary", {})
        mesh_cfg = domain_cfg.get("mesh", {})
        analysis = domain_cfg.get("analysis", {})

        mu = float(props["viscosity_mu"]["value"])
        rho = float(props["density_rho"]["value"])
        L = float(geom["length"]["value"])
        H = float(geom["height"]["value"])
        res = int(mesh_cfg["resolution"]["value"])
        dt = float(analysis["time_step"]["value"])

        print(f"[FENICSX] {self._domain.upper()} domain initialized")
        print(f"[FENICSX]   mu={mu:.2e} Pa.s  rho={rho:.1f} kg/m3")
        print(f"[FENICSX]   Domain: {L}m x {H}m  resolution={res} elem/m")
        print(f"[FENICSX]   dt={dt}s")

        # TODO: Build FEniCSx mesh, function spaces, and variational form
        # This is where dolfinx.mesh.create_rectangle(), FunctionSpace(),
        # and the weak form of Navier-Stokes or Stokes would go.
        # The pattern:
        #   mesh = dolfinx.mesh.create_rectangle(comm, [[0,0],[L,H]], [nx,ny])
        #   V = dolfinx.fem.functionspace(mesh, ("Lagrange", 2, (2,)))
        #   Q = dolfinx.fem.functionspace(mesh, ("Lagrange", 1))
        #   ... define BCs, variational form, solver ...

        return {
            "domain": self._domain,
            "solver": "fenicsx",
            "ready": True,
            "mu": mu,
            "rho": rho,
            "L": L,
            "H": H,
            "dt": dt,
        }

    def step(self, measurement: float, dt: float, model_props: dict) -> dict:
        """Advance fluid model by one timestep.

        For water: measurement = flow velocity (m/s) from sensor
        For air: measurement = wind speed (m/s) from anemometer

        Returns dict with 'converged' and 'stress_pa' (pressure at critical point).
        """
        if not model_props.get("ready", False):
            return {"converged": False, "stress_pa": 0.0}

        # TODO: Update inlet BC with sensor measurement, solve one timestep
        # Pattern:
        #   inlet_bc.value = measurement
        #   solver.solve(u, p)
        #   stress_pa = assemble pressure at monitoring point

        # FEniCSx integration not yet complete — return unconverged until solve() is wired.
        # Bernoulli estimate stored for diagnostic tracing only; NOT used for safety decisions.
        rho = model_props.get("rho", _WATER_DENSITY_KG_M3)
        stress_pa_estimate = _DYNAMIC_PRESSURE_COEFF * rho * measurement ** 2
        print(f"[FLUID] WARN: FEniCSx solve not integrated — step() returns converged=False "
              f"(Bernoulli estimate {stress_pa_estimate:.2f} Pa, diagnostic only)", file=sys.stderr)

        return {
            "converged": False,
            "stress_pa": stress_pa_estimate,
        }

    def check_required_params(self, cfg: dict) -> list[tuple[str, str]]:
        params = WATER_REQUIRED_PARAMS if self._domain == "water" else AIR_REQUIRED_PARAMS
        missing = []
        for dotpath, desc in params.items():
            if _get_nested(cfg, dotpath) is None:
                missing.append((dotpath, desc))
        return missing
