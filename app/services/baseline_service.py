"""
Service layer for loading the saved baseline model artifact
and generating predictions.
"""

from pathlib import Path
import joblib
import pandas as pd

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "artifacts" / "baseline_model.joblib"


def load_artifact():
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"Baseline model artifact not found at {ARTIFACT_PATH}. "
            "Run `python -m models.train_baseline` first."
        )
    return joblib.load(ARTIFACT_PATH)


def predict_baseline(payload: dict) -> float:
    artifact = load_artifact()
    model = artifact["model"]
    feature_cols = artifact["feature_cols"]

    # Convert request payload to one-row DataFrame in the exact feature order
    X = pd.DataFrame([payload])[feature_cols]
    pred = model.predict(X)[0]
    return float(pred)