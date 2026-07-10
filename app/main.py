from fastapi import FastAPI, Query
import pandas as pd
from app.db import engine
from app.services.scenario_service import run_price_scenario

app = FastAPI(title="RGM OS API")


@app.get("/")
def root():
    return {"message": "RGM OS API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/kpi-summary")
def kpi_summary():
    query = """
    SELECT
        SUM(revenue) AS total_revenue,
        SUM(units_sold) AS total_units,
        AVG(revenue) AS avg_weekly_revenue,
        AVG(units_sold) AS avg_weekly_units,
        COUNT(DISTINCT item_id) AS unique_items,
        COUNT(DISTINCT store_id) AS unique_stores
    FROM rgm.fact_sales_weekly
    """
    df = pd.read_sql(query, engine)
    return df.iloc[0].to_dict()


@app.get("/promo-diagnostics")
def promo_diagnostics(limit: int = 25):
    query = f"""
    SELECT
        item_id,
        store_id,
        COUNT(*) AS total_weeks,
        SUM(CASE WHEN promo_flag = 1 THEN 1 ELSE 0 END) AS promo_weeks,
        AVG(discount_pct) AS avg_discount_pct,
        AVG(units_sold) AS avg_units,
        AVG(revenue) AS avg_revenue
    FROM rgm.feature_rgm_weekly
    GROUP BY item_id, store_id
    ORDER BY promo_weeks DESC, avg_discount_pct DESC
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return {"rows": df.to_dict(orient="records")}


@app.get("/forecast")
def forecast(item_id: str = Query(...), store_id: str = Query(...)):
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
        return {"error": "No rows found for this item/store pair."}

    from pathlib import Path
    import joblib

    artifact_path = Path(__file__).resolve().parents[1] / "models" / "artifacts" / "baseline_model.joblib"
    artifact = joblib.load(artifact_path)
    model = artifact["model"]
    feature_cols = artifact["feature_cols"]

    row = df.iloc[0].copy()
    X = row[feature_cols].to_frame().T.fillna(0)
    pred = float(model.predict(X)[0])

    return {
        "item_id": item_id,
        "store_id": store_id,
        "week_start_date": str(row["week_start_date"]),
        "current_price": float(row["sell_price"]) if pd.notna(row["sell_price"]) else None,
        "predicted_units_next_week_like_state": pred
    }


@app.get("/scenario")
def scenario(
    item_id: str = Query(...),
    store_id: str = Query(...),
    new_price: float = Query(...)
):
    return run_price_scenario(item_id=item_id, store_id=store_id, new_price=new_price)