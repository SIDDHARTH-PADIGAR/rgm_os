"""
Forecast service.

Purpose:
Serve actual vs predicted weekly demand for a selected item-store pair.

How it works:
- pulls rows from rgm.feature_rgm_weekly
- loads trained LightGBM artifact
- runs predictions
- returns a clean JSON-friendly list for charting
"""

from pathlib import Path
import joblib
import pandas as pd
from app.db import engine

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "artifacts" / "baseline_model.joblib"


def _load_model_artifact():
    artifact = joblib.load(ARTIFACT_PATH)
    return artifact["model"], artifact["feature_cols"]


def get_forecast(item_id: str, store_id: str):
    query = f"""
    SELECT *
    FROM rgm.feature_rgm_weekly
    WHERE item_id = '{item_id}'
      AND store_id = '{store_id}'
    ORDER BY week_start_date
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return {
            "item_id": item_id,
            "store_id": store_id,
            "rows": []
        }

    model, feature_cols = _load_model_artifact()

    X = df[feature_cols].fillna(0)
    df["predicted_units"] = model.predict(X)

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "week_start_date": str(r["week_start_date"]),
            "wm_yr_wk": int(r["wm_yr_wk"]),
            "actual_units": float(r["units_sold"]),
            "predicted_units": float(r["predicted_units"]),
            "sell_price": float(r["sell_price"]) if pd.notna(r["sell_price"]) else None,
            "revenue": float(r["revenue"]) if pd.notna(r["revenue"]) else None,
            "is_event_week": int(r["is_event_week"]) if pd.notna(r["is_event_week"]) else 0,
            "snap_flag": int(r["snap_flag"]) if pd.notna(r["snap_flag"]) else 0,
        })

    return {
        "item_id": item_id,
        "store_id": store_id,
        "rows": rows
    }