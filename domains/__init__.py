# domains/ — Domain Registry backends
# Each domain implements DomainBackend ABC (see base.py).
# Load a domain: DomainBackend.load_registry("structural")
from domains.base import DomainBackend, DomainRegistry

__all__ = ["DomainBackend", "DomainRegistry"]
