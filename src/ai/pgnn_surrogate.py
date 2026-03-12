"""
src/ai/pgnn_surrogate.py — PgNN Surrogate Bridge from Hybrid-Digital-Twin
==========================================================================
Integrates the Physics-Guided Neural Network (PgNN) from the
Hybrid-Digital-Twin-Seismic-RC project as a fast inference module
within the Belico Stack pipeline.

The PgNN achieves ~5000x speedup over full NLTHA (2ms vs 10s per record),
enabling real-time inter-story drift ratio (IDR) prediction from
ground-motion acceleration time series.

Usage in Belico Stack:
    from src.ai.pgnn_surrogate import PgNNSurrogate

    surrogate = PgNNSurrogate(model_path="path/to/pinn_best.pt")
    idr_prediction = surrogate.predict(accel_array_g, dt=0.01)

Dependencies:
    - torch >= 2.0.0
    - numpy
    - The HybridPINN model class (loaded from checkpoint, self-contained)
"""

import json
import logging
import time
from pathlib import Path

import numpy as np
try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default path to the Hybrid-Twin model
HYBRID_TWIN_ROOT = Path.home() / "Hybrid-Digital-Twin-Seismic-RC"
DEFAULT_MODEL_DIR = HYBRID_TWIN_ROOT / "data" / "models"
DEFAULT_PROCESSED_DIR = HYBRID_TWIN_ROOT / "data" / "processed" / "peer_10story_seq"


class PgNNSurrogate:
    """Wrapper for the HybridPINN model from the Hybrid-Digital-Twin project.

    Provides a clean interface for the Belico Stack to run real-time
    seismic response predictions without depending on full NLTHA.

    Parameters
    ----------
    model_path : Path or str
        Path to the pinn_best.pt checkpoint file.
    processed_dir : Path or str, optional
        Path to the processed data directory (for scaler_params.json).
    device : str
        Torch device ('cpu' or 'cuda').
    """

    def __init__(
        self,
        model_path: Path = None,
        processed_dir: Path = None,
        device: str = "cpu",
    ):
        self.device = torch.device(device)
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_DIR / "pinn_best.pt"
        self.processed_dir = Path(processed_dir) if processed_dir else DEFAULT_PROCESSED_DIR
        self.model = None
        self.scaler = None
        self.seq_len = 2048
        self.n_stories = None
        if not _TORCH_AVAILABLE:
            logger.warning(
                "PgNN surrogate unavailable: torch not installed. Run: pip install torch"
            )
            return
        self._load()

    def _load(self):
        """Load model checkpoint and scaler parameters."""
        if not self.model_path.exists():
            logger.warning(
                "PgNN checkpoint not found at %s. "
                "Surrogate predictions will not be available.",
                self.model_path,
            )
            return

        try:
            import sys

            # Temporarily isolate Hybrid-Twin's 'src' from belico-stack's 'src'
            # by saving and removing the current 'src' module tree, importing
            # the Hybrid-Twin model, then restoring belico-stack's modules.
            saved_modules = {}
            for key in list(sys.modules):
                if key == "src" or key.startswith("src."):
                    saved_modules[key] = sys.modules.pop(key)

            hybrid_root = str(HYBRID_TWIN_ROOT)
            sys.path.insert(0, hybrid_root)
            try:
                from src.pinn.model import HybridPINN
            finally:
                # Restore belico-stack's src modules
                for key in list(sys.modules):
                    if key == "src" or key.startswith("src."):
                        sys.modules.pop(key, None)
                sys.modules.update(saved_modules)
                sys.path.remove(hybrid_root)

            self.model = HybridPINN.from_checkpoint(self.model_path)
            self.model.to(self.device)
            self.model.eval()

            # Extract config
            self.seq_len = self.model.config.seq_len
            self.n_stories = self.model.config.n_stories

            logger.info(
                "PgNN surrogate loaded: n_stories=%d, seq_len=%d, params=%d",
                self.n_stories,
                self.seq_len,
                self.model.count_parameters(),
            )

            # Load scaler if available
            scaler_path = self.processed_dir / "scaler_params.json"
            if scaler_path.exists():
                with open(scaler_path) as f:
                    self.scaler = json.load(f)
                logger.info("Scaler loaded from %s", scaler_path)

        except (ImportError, RuntimeError, AttributeError, OSError, ValueError) as e:
            logger.error("Failed to load PgNN surrogate: %s", e)
            self.model = None

    @property
    def is_available(self) -> bool:
        """Check if the surrogate model is loaded and ready."""
        return self.model is not None

    def _prepare_input(self, accel_ms2: np.ndarray) -> torch.Tensor:
        """Normalize and reshape acceleration array for model input.

        Parameters
        ----------
        accel_ms2 : np.ndarray
            Acceleration time series in m/s^2.

        Returns
        -------
        torch.Tensor of shape (1, 1, seq_len)
        """
        accel = accel_ms2.astype(np.float32)
        mu, sigma = accel.mean(), accel.std()
        if sigma < 1e-8:
            sigma = 1.0
        accel = (accel - mu) / sigma

        # Pad or truncate to seq_len
        if len(accel) >= self.seq_len:
            accel = accel[: self.seq_len]
        else:
            pad = np.zeros(self.seq_len - len(accel), dtype=np.float32)
            accel = np.concatenate([accel, pad])

        return torch.from_numpy(accel).unsqueeze(0).unsqueeze(0).to(self.device)

    def predict(self, accel_g: np.ndarray, dt: float = 0.01) -> dict:
        """Predict inter-story drift ratios from ground-motion acceleration.

        Parameters
        ----------
        accel_g : np.ndarray
            Acceleration time series in units of 'g'.
        dt : float
            Time step in seconds.

        Returns
        -------
        dict with keys:
            'idr': np.ndarray of peak IDR per story (dimensionless)
            'n_stories': int
            'latency_ms': float (inference time)
            'source': str
        """
        if not self.is_available:
            return {
                "idr": None,
                "n_stories": 0,
                "latency_ms": 0.0,
                "source": "unavailable",
                "error": "PgNN model not loaded",
            }

        # Convert g to m/s^2
        accel_ms2 = accel_g * 9.81
        x = self._prepare_input(accel_ms2)

        # Inference
        t0 = time.perf_counter()
        with torch.no_grad():
            pred = self.model(x)
        latency_ms = (time.perf_counter() - t0) * 1000

        # Denormalize output
        idr = pred.squeeze(0).cpu().numpy()
        if self.scaler and "target" in self.scaler:
            mean = np.array(self.scaler["target"]["mean"])
            std = np.array(self.scaler["target"]["std"])
            # Only apply scaler if dimensions match (scaler may be from
            # a different n_stories experiment)
            if mean.shape[0] == idr.shape[0]:
                if idr.ndim == 2:  # Seq2Seq: (n_stories, T)
                    idr = idr * std[:, None] + mean[:, None]
                else:  # Scalar: (n_stories,)
                    idr = idr * std + mean
            else:
                logger.debug(
                    "Scaler n_stories=%d != model n_stories=%d, skipping denorm",
                    mean.shape[0], idr.shape[0],
                )

        return {
            "idr": idr,
            "n_stories": self.n_stories,
            "latency_ms": latency_ms,
            "source": "PgNN_surrogate",
        }

    def predict_with_alarm(
        self, accel_g: np.ndarray, dt: float = 0.01, collapse_threshold: float = 0.025
    ) -> dict:
        """Predict IDR and evaluate collapse risk per story.

        Parameters
        ----------
        accel_g : np.ndarray
            Acceleration in 'g'.
        dt : float
            Time step.
        collapse_threshold : float
            IDR threshold for collapse risk (default 2.5%).

        Returns
        -------
        dict with additional keys:
            'alarm': bool (True if any story exceeds threshold)
            'critical_stories': list of story indices exceeding threshold
        """
        result = self.predict(accel_g, dt)
        if result["idr"] is None:
            result["alarm"] = False
            result["critical_stories"] = []
            return result

        idr = result["idr"]
        # For Seq2Seq output (n_stories, T), take peak absolute IDR per story
        if idr.ndim == 2:
            peak_idr = np.abs(idr).max(axis=1)
        else:
            peak_idr = np.abs(idr)
        result["peak_idr"] = peak_idr

        critical = [
            i + 1 for i, v in enumerate(peak_idr) if v > collapse_threshold
        ]
        result["alarm"] = len(critical) > 0
        result["critical_stories"] = critical
        return result
