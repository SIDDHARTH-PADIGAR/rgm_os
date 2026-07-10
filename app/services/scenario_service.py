"""
Scenario service for bounded RGM price simulation.

Important:
This service only supports LOCAL price moves around the current price.
It is not meant for extreme price shocks.
"""

from pathlib import Path
import joblib
import pandas as pd
from app.db import engine

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "artifacts" / "baseline_model.joblib"

# hard guardrail for scenario simulation
MAX_PRICE_MOVE_PCT = 0.15  # +/- 15%


def _load_model_artifact():
    artifact = joblib.load(ARTIFACT_PATH)
    return artifact["model"], artifact["feature_cols"]


def run_price_scenario(item_id: str, store_id: str, new_price: float):
    query = f"""
    SELECT *
    FROM rgm.feature_rgm_weekly
    WHERE item_id = '{item_id}'
      AND store_id = '{store_id}'
    ORDER BY week_start_date DESC
    LIMIT 1
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return {
            "item_id": item_id,
            "store_id": store_id,
            "error": "No feature rows found for this item/store pair."
        }

    row = df.iloc[0].copy()

    model, feature_cols = _load_model_artifact()

    current_price = float(row["sell_price"]) if pd.notna(row["sell_price"]) else None
    if current_price is None or current_price <= 0:
        return {
            "item_id": item_id,
            "store_id": store_id,
            "error": "Current price is missing or invalid for this item/store pair."
        }

    historical_min_price = float(row["historical_min_price"]) if pd.notna(row["historical_min_price"]) else current_price
    historical_max_price = float(row["historical_max_price"]) if pd.notna(row["historical_max_price"]) else current_price

    allowed_min_price = round(current_price * (1 - MAX_PRICE_MOVE_PCT), 4)
    allowed_max_price = round(current_price * (1 + MAX_PRICE_MOVE_PCT), 4)

    # hard local-move guardrail
    if new_price < allowed_min_price or new_price > allowed_max_price:
        return {
            "item_id": item_id,
            "store_id": store_id,
            "current_price": current_price,
            "requested_new_price": new_price,
            "allowed_price_range_local": [allowed_min_price, allowed_max_price],
            "historical_price_range": [historical_min_price, historical_max_price],
            "error": (
                f"Scenario price must be within +/-15% of current price. "
                f"Allowed range: {allowed_min_price} to {allowed_max_price}"
            )
        }

    warnings = []

    # softer historical-support warning
    if new_price < historical_min_price or new_price > historical_max_price:
        warnings.append(
            "Scenario price is outside the observed historical price range for this item-store pair. Treat output as directional."
        )

    baseline_row = row.copy()
    baseline_x = baseline_row[feature_cols].to_frame().T.fillna(0)
    baseline_units = float(model.predict(baseline_x)[0])

    scenario_row = row.copy()
    scenario_row["sell_price"] = new_price

    lag_1_price = float(row["lag_1_price"]) if pd.notna(row["lag_1_price"]) and row["lag_1_price"] > 0 else current_price
    rolling_4w_price_mean = float(row["rolling_4w_price_mean"]) if pd.notna(row["rolling_4w_price_mean"]) and row["rolling_4w_price_mean"] > 0 else current_price

    scenario_row["lag_1_price"] = lag_1_price
    scenario_row["rolling_4w_price_mean"] = rolling_4w_price_mean

    # recompute scenario price-response features
    scenario_row["price_change_pct_1w"] = (new_price - lag_1_price) / lag_1_price if lag_1_price > 0 else 0.0
    scenario_row["price_vs_rolling_4w_pct"] = (new_price - rolling_4w_price_mean) / rolling_4w_price_mean if rolling_4w_price_mean > 0 else 0.0

    if new_price < rolling_4w_price_mean:
        scenario_row["promo_flag"] = 1
        scenario_row["discount_pct"] = (rolling_4w_price_mean - new_price) / rolling_4w_price_mean
    else:
        scenario_row["promo_flag"] = 0
        scenario_row["discount_pct"] = 0.0

    scenario_x = scenario_row[feature_cols].to_frame().T.fillna(0)
    scenario_units = float(model.predict(scenario_x)[0])

    baseline_revenue = baseline_units * current_price
    scenario_revenue = scenario_units * new_price

    return {
        "item_id": item_id,
        "store_id": store_id,
        "current_price": current_price,
        "new_price": new_price,
        "allowed_price_range_local": [allowed_min_price, allowed_max_price],
        "historical_price_range": [historical_min_price, historical_max_price],
        "baseline_predicted_units": baseline_units,
        "scenario_predicted_units": scenario_units,
        "delta_units": scenario_units - baseline_units,
        "baseline_predicted_revenue": baseline_revenue,
        "scenario_predicted_revenue": scenario_revenue,
        "delta_revenue": scenario_revenue - baseline_revenue,
        "warnings": warnings
    }