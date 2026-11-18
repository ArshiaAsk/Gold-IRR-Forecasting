"""
Load and run the committed stationary model.

One job: given a (sequence_length, n_features) window produced by
``src.feature_eng.prepare_model_input``, return the next-trading-day log
return. All model facts (architecture, sequence length, feature order, seed,
training window) come from the metadata file that sits next to the artifact —
nothing about the model is hardcoded here.

Used by both the FastAPI service and the Streamlit app, so the two cannot
disagree about how a window is scaled or which model is loaded.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
METADATA_NAME = "gold_lstm_stationary_v2.metadata.json"


class ArtifactMissing(RuntimeError):
    """The model, a scaler or the metadata file is absent."""

    def __init__(self, paths: List[Path]):
        self.paths = [str(p) for p in paths]
        super().__init__(
            "Model artifacts are missing: " + ", ".join(self.paths)
        )


@dataclass
class ServingBundle:
    """The loaded artifact plus the metadata that describes it."""

    model: Any
    scaler_X: Any
    scaler_y: Any
    metadata: Dict[str, Any]
    model_path: Path
    metadata_path: Path
    _lock: threading.Lock

    @property
    def sequence_length(self) -> int:
        return int(self.metadata["sequence_length"])

    @property
    def feature_columns(self) -> List[str]:
        return list(self.metadata["feature_columns"])

    @property
    def n_features(self) -> int:
        return len(self.feature_columns)

    @property
    def model_id(self) -> str:
        return Path(self.metadata["artifact"]).stem

    def predict_log_return(self, X: np.ndarray) -> float:
        """
        Scale ``X`` with the training scaler, run the model, invert the target.

        Args:
            X: (sequence_length, n_features) array from the shared feature code.

        Returns:
            Predicted next-trading-day log return, in the units the scaler_y
            was fitted on (log returns).
        """
        X = np.asarray(X, dtype=float)
        expected = (self.sequence_length, self.n_features)
        if X.shape != expected:
            raise ValueError(f"expected input shape {expected}, got {X.shape}")

        scaled = self.scaler_X.transform(X).reshape(1, *expected)
        with self._lock:
            # Keras inference on one model object is not documented as
            # thread-safe; one forward pass is cheap, so serialise it.
            pred_scaled = self.model.predict(scaled, verbose=0)
        log_return = self.scaler_y.inverse_transform(
            np.asarray(pred_scaled).reshape(-1, 1)
        )[0, 0]
        return float(log_return)


def load_metadata(path: Path = MODELS_DIR / METADATA_NAME) -> Dict[str, Any]:
    """Read the artifact metadata. Raises ``ArtifactMissing`` if absent."""
    path = Path(path)
    if not path.exists():
        raise ArtifactMissing([path])
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_bundle(models_dir: Path = MODELS_DIR) -> ServingBundle:
    """
    Load the model, both scalers and the metadata exactly once.

    Paths are taken from the metadata's ``artifact`` and ``scalers`` entries,
    resolved against ``models_dir``, so moving the artifact does not require a
    code change as long as the metadata moves with it.
    """
    models_dir = Path(models_dir)
    metadata_path = models_dir / METADATA_NAME
    metadata = load_metadata(metadata_path)

    model_path = models_dir / Path(metadata["artifact"]).name
    scaler_paths = [models_dir / Path(p).name for p in metadata["scalers"]]
    missing = [p for p in [model_path, *scaler_paths] if not p.exists()]
    if missing:
        raise ArtifactMissing(missing)

    import keras

    # compile=False: inference only, and it avoids re-running the optimizer
    # config that the legacy artifact needed workarounds for.
    model = keras.models.load_model(str(model_path), compile=False)
    scaler_X, scaler_y = (joblib.load(str(p)) for p in scaler_paths)

    if scaler_X.n_features_in_ != len(metadata["feature_columns"]):
        raise ValueError(
            f"scaler_X expects {scaler_X.n_features_in_} features, metadata "
            f"lists {len(metadata['feature_columns'])}"
        )
    if tuple(model.input_shape[1:]) != (
        int(metadata["sequence_length"]),
        len(metadata["feature_columns"]),
    ):
        raise ValueError(
            f"model input shape {model.input_shape} disagrees with metadata"
        )

    logger.info("Loaded %s (%d params) from %s", metadata["artifact"],
                int(model.count_params()), model_path)
    return ServingBundle(
        model=model,
        scaler_X=scaler_X,
        scaler_y=scaler_y,
        metadata=metadata,
        model_path=model_path,
        metadata_path=metadata_path,
        _lock=threading.Lock(),
    )
