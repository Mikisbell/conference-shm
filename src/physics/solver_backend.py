"""
src/physics/solver_backend.py — Abstract Solver Backend Interface
=================================================================
Every domain solver (structural, fluid, aero) must implement this interface.
This allows bridge.py to work with any domain without knowing the internals.

Domains:
  structural  -> OpenSeesPy   (torture_chamber.py)
  water       -> FEniCSx      (torture_chamber_fluid.py)
  air         -> FEniCSx/SU2  (torture_chamber_fluid.py with air params)

Pattern:
  backend = get_solver_backend(cfg)
  props = backend.init_model(cfg)
  result = backend.step(measurement, dt, props)
"""

from abc import ABC, abstractmethod

try:
    from src.physics.torture_chamber import StructuralBackend
except ImportError:
    StructuralBackend = None  # type: ignore

try:
    from src.physics.torture_chamber_fluid import FluidBackend
except ImportError:
    FluidBackend = None  # type: ignore


class SolverBackend(ABC):
    """Interface that every physics solver must implement."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain name: 'structural', 'water', or 'air'."""

    @abstractmethod
    def init_model(self, cfg: dict) -> dict:
        """Initialize the solver model from SSOT config.

        Args:
            cfg: Full SSOT dictionary from config/params.yaml.

        Returns:
            dict with model properties needed by step().
            Must include at minimum:
              - 'domain': str
              - 'solver': str (e.g. 'openseespy', 'fenicsx')
              - 'ready': bool
        """

    @abstractmethod
    def step(self, measurement: float, dt: float, model_props: dict) -> dict:
        """Advance the model by one timestep with a sensor measurement.

        Args:
            measurement: Sensor reading (accel_g for structural,
                         velocity_m_s for water, pressure_pa for air).
            dt: Timestep in seconds.
            model_props: Dict returned by init_model().

        Returns:
            dict with at minimum:
              - 'converged': bool
              - 'stress_pa': float (or equivalent demand metric)
        """

    @abstractmethod
    def check_required_params(self, cfg: dict) -> list[tuple[str, str]]:
        """Return list of (dotpath, description) for missing required params.

        Used by scaffold_investigation.py to generate the data checklist.
        Returns empty list if all required params are populated.
        """


def get_solver_backend(cfg: dict) -> SolverBackend:
    """Factory: return the correct solver backend based on SSOT domain field.

    Falls back to 'structural' if domain is not specified.
    """
    domain = cfg.get("project", {}).get("domain", "structural")

    if domain == "structural":
        if StructuralBackend is None:
            print("[SOLVER] ERROR: StructuralBackend unavailable — openseespy may not be installed.",
                  flush=True)
            raise RuntimeError("StructuralBackend could not be imported (src.physics.torture_chamber).")
        return StructuralBackend()
    elif domain in ("water", "air"):
        if FluidBackend is None:
            print("[SOLVER] ERROR: FluidBackend unavailable — dolfinx/FEniCSx may not be installed.",
                  flush=True)
            raise RuntimeError("FluidBackend could not be imported (src.physics.torture_chamber_fluid).")
        return FluidBackend(domain=domain)
    else:
        raise ValueError(
            f"Unknown domain '{domain}' in SSOT. "
            f"Valid domains: structural, water, air"
        )
