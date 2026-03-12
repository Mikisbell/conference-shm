"""tools/adapters — Concrete DataAdapter implementations for each source type."""

from tools.adapters.local_file import LocalFileAdapter
from tools.adapters.rest_json import RestJsonAdapter
from tools.adapters.rest_csv import RestCsvAdapter
from tools.adapters.fred import FredAdapter
from tools.adapters.physionet import PhysioNetAdapter
from tools.adapters.nasa_earthdata import NasaEarthdataAdapter
from tools.adapters.kaggle import KaggleAdapter

ADAPTER_REGISTRY: dict[str, type] = {
    "local_file":      LocalFileAdapter,
    "rest_json":       RestJsonAdapter,
    "rest_csv":        RestCsvAdapter,
    "fred":            FredAdapter,
    "physionet":       PhysioNetAdapter,
    "nasa_earthdata":  NasaEarthdataAdapter,
    "kaggle":          KaggleAdapter,
}


def get_adapter(adapter_type: str):
    """Return adapter class for the given type string. Raises KeyError if unknown."""
    if adapter_type not in ADAPTER_REGISTRY:
        raise KeyError(
            f"[adapters] Unknown adapter type '{adapter_type}'. "
            f"Available: {list(ADAPTER_REGISTRY)}"
        )
    return ADAPTER_REGISTRY[adapter_type]
