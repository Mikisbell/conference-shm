"""
domains/base.py — Domain Registry + DomainBackend ABC
======================================================

Every research domain in belico-stack is declared as:
  1. A YAML descriptor  : config/domains/<domain>.yaml
  2. A Python backend   : domains/<domain>.py (class extending DomainBackend)

The orchestrator (CLAUDE.md) reads config/params.yaml → project.domain,
then calls DomainRegistry.load("<domain>") to get the live backend.

Usage (orchestrator-level):
    from domains.base import DomainRegistry
    backend = DomainRegistry.load("structural")
    deps_ok = backend.validate_ssot()
    result  = backend.run_compute(params)

Usage (subagent — read registry only, no backend needed):
    from domains.base import DomainRegistry
    registry = DomainRegistry.get_registry("environmental")
    print(registry["solver"]["engine"])
"""

from __future__ import annotations

import importlib
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

# ─── Registry path ────────────────────────────────────────────────────────────
_DOMAINS_CONFIG_DIR = Path(__file__).parent.parent / "config" / "domains"


class DomainRegistry:
    """Static factory — loads domain YAML descriptors and optional backends."""

    @staticmethod
    def get_registry(domain: str) -> dict[str, Any]:
        """Return the raw YAML registry dict for a domain (no backend loaded).

        Args:
            domain: Domain name (e.g. "structural", "environmental").

        Returns:
            Parsed YAML dict from config/domains/<domain>.yaml.

        Raises:
            FileNotFoundError: If the domain registry file does not exist.
            yaml.YAMLError: If the file is malformed.
        """
        registry_path = _DOMAINS_CONFIG_DIR / f"{domain}.yaml"
        if not registry_path.exists():
            available = [p.stem for p in _DOMAINS_CONFIG_DIR.glob("*.yaml")]
            raise FileNotFoundError(
                f"[DomainRegistry] No registry found for domain '{domain}'. "
                f"Available: {available}. "
                f"To add a domain, create config/domains/{domain}.yaml."
            )
        with registry_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    @staticmethod
    def list_domains() -> list[dict[str, str]]:
        """List all registered domains with their status.

        Returns:
            List of dicts with keys: domain, display_name, status.
        """
        result = []
        for path in sorted(_DOMAINS_CONFIG_DIR.glob("*.yaml")):
            try:
                with path.open("r", encoding="utf-8") as fh:
                    reg = yaml.safe_load(fh)
                result.append({
                    "domain": reg.get("domain", path.stem),
                    "display_name": reg.get("display_name", ""),
                    "status": reg.get("status", "unknown"),
                })
            except yaml.YAMLError as exc:
                print(
                    f"[DomainRegistry] WARN: Could not parse {path.name}: {exc}",
                    file=sys.stderr,
                )
        return result

    @staticmethod
    def load(domain: str) -> "DomainBackend":
        """Load the Python backend for a domain.

        Imports domains.<domain> and instantiates the class declared in
        registry['solver']['backend_class'].

        Args:
            domain: Domain name (e.g. "structural").

        Returns:
            Instantiated DomainBackend subclass.

        Raises:
            FileNotFoundError: Registry YAML not found.
            ImportError: Backend module not importable.
            AttributeError: Backend class not found in module.
        """
        registry = DomainRegistry.get_registry(domain)
        backend_module = registry.get("solver", {}).get("backend_module")
        backend_class = registry.get("solver", {}).get("backend_class")

        if not backend_module or not backend_class:
            raise ImportError(
                f"[DomainRegistry] Domain '{domain}' registry is missing "
                "'solver.backend_module' or 'solver.backend_class'."
            )

        try:
            module = importlib.import_module(backend_module)
        except ImportError as exc:
            raise ImportError(
                f"[DomainRegistry] Cannot import backend '{backend_module}' "
                f"for domain '{domain}': {exc}"
            ) from exc

        cls = getattr(module, backend_class, None)
        if cls is None:
            raise AttributeError(
                f"[DomainRegistry] Class '{backend_class}' not found in "
                f"module '{backend_module}'."
            )

        instance = cls(registry=registry)
        if not isinstance(instance, DomainBackend):
            raise TypeError(
                f"[DomainRegistry] '{backend_class}' must extend DomainBackend."
            )
        return instance


class DomainBackend(ABC):
    """Abstract base class for all domain backends.

    Every domain (structural, environmental, biomedical, economics …)
    must implement these 4 methods. The pipeline (COMPUTE C0-C5,
    emulator, narrator, plot_figures) calls these methods via the registry
    instead of hardcoding domain-specific logic.

    Constructor:
        registry (dict): Raw YAML registry dict from DomainRegistry.get_registry().
    """

    def __init__(self, registry: dict[str, Any]) -> None:
        self._registry = registry
        self._domain = registry.get("domain", "unknown")

    # ── 1. Dependencies ───────────────────────────────────────────────────────

    @abstractmethod
    def get_dependencies(self) -> dict[str, list[str]]:
        """Return Python and system dependencies required by this domain.

        Returns:
            Dict with keys:
              "python"  → list of pip package specifiers (e.g. ["openseespy>=3.4"])
              "system"  → list of system package names  (e.g. ["gdal"])
              "optional"→ list of optional pip packages (may be empty)

        Example:
            {"python": ["openseespy>=3.4", "numpy>=1.24"],
             "system": [],
             "optional": []}
        """

    # ── 2. Compute ────────────────────────────────────────────────────────────

    @abstractmethod
    def run_compute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the domain-specific compute pipeline (COMPUTE C2).

        This is the core numerical computation for the domain:
        - structural : run OpenSeesPy transient analysis
        - environmental : download + process GIS / remote sensing data
        - biomedical : extract biosignal features, run ML pipeline
        - economics : run econometric estimation

        Args:
            params: Merged SSOT params from config/params.yaml
                    (filtered to domain namespace).

        Returns:
            Dict with at minimum:
              "converged"  → bool  (True if compute succeeded)
              "outputs"    → dict  (domain-specific result summary)
              "files"      → list[str]  (paths written to data/processed/)

        On failure: return {"converged": False, "error": "<diagnostic message>"}
        NEVER return converged=True with fabricated data.
        """

    # ── 3. SSOT validation ────────────────────────────────────────────────────

    @abstractmethod
    def validate_ssot(self) -> tuple[bool, list[str]]:
        """Validate that config/params.yaml contains the required keys for this domain.

        This runs at COMPUTE C0 to catch missing params before the simulation
        fails with a cryptic KeyError deep in the solver.

        Returns:
            Tuple (ok: bool, errors: list[str])
              ok=True  → SSOT is complete, compute can proceed
              ok=False → errors contains human-readable missing-key messages

        Example:
            ok, errors = backend.validate_ssot()
            if not ok:
                for e in errors: print(e, file=sys.stderr)
                sys.exit(1)
        """

    # ── 4. Emulator ───────────────────────────────────────────────────────────

    @abstractmethod
    def get_emulator(self) -> dict[str, Any] | None:
        """Return emulator configuration for COMPUTE C3, or None if not applicable.

        For domains without hardware emulation (environmental, biomedical,
        economics), return None. The pipeline will skip C3 automatically.

        Returns:
            None if no emulator available for this domain, OR
            Dict with keys:
              "tool"   → str  (e.g. "tools/arduino_emu.py")
              "modes"  → list[str]  (available emulation modes)
              "launch" → str  (command template to launch the emulator)

        Example (structural):
            {"tool": "tools/arduino_emu.py",
             "modes": ["sano", "resonance", "dano_leve", "dano_critico"],
             "launch": "python3 tools/arduino_emu.py {mode} {freq_hz}"}
        """

    # ── Concrete helpers (shared by all domains) ──────────────────────────────

    def get_registry(self) -> dict[str, Any]:
        """Return the raw YAML registry dict for introspection."""
        return self._registry

    def domain_name(self) -> str:
        """Return the canonical domain name (e.g. 'structural')."""
        return self._domain

    def get_apis(self) -> dict[str, dict[str, str]]:
        """Return API configuration dict from the registry."""
        return self._registry.get("apis", {})

    def get_params_namespace(self) -> list[str]:
        """Return the list of SSOT param namespaces for this domain."""
        return self._registry.get("params_namespace", [])

    def get_normative_codes(self) -> list[str]:
        """Return normative codes applicable to this domain."""
        return self._registry.get("pipeline", {}).get("normative_codes", [])

    def narrator_flag(self) -> str:
        """Return the --domain flag for scientific_narrator.py."""
        return self._registry.get("pipeline", {}).get("narrator_flag", "")

    def plot_figures_flag(self) -> str:
        """Return the --domain flag for plot_figures.py."""
        return self._registry.get("pipeline", {}).get("plot_figures_flag", "")

    def __repr__(self) -> str:
        status = self._registry.get("status", "unknown")
        return f"<DomainBackend domain={self._domain!r} status={status!r}>"
