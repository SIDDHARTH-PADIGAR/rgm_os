"""
Promo diagnostics service.

Purpose:
Identify discounting / promo pressure behavior using price deviation
from a rolling base price proxy already present in rgm.feature_rgm_weekly.

This is not perfect trade-promo measurement.
It is a pricing / promo pressure diagnostic layer for the project.
"""

import pandas as pd
from app.db import engine


def get_promo_diagnostics(limit: int = 25):
    query = f"""
    WITH base AS (
        SELECT
            item_id,
            store_id,
            week_start_date,
            sell_price,
            units_sold,
            revenue,
            rolling_4w_price_mean,
            CASE
                WHEN rolling_4w_price_mean IS NOT NULL AND rolling_4w_price_mean <> 0
                THEN (sell_price - rolling_4w_price_mean) / rolling_4w_price_mean
                ELSE NULL
            END AS discount_pct_to_recent_base
        FROM rgm.feature_rgm_weekly
    ),
    agg AS (
        SELECT
            item_id,
            store_id,
            COUNT(*) AS total_weeks,
            AVG(discount_pct_to_recent_base) AS avg_discount_pct,
            SUM(
                CASE WHEN discount_pct_to_recent_base <= -0.05 THEN 1 ELSE 0 END
            ) AS promo_weeks,
            AVG(units_sold) AS avg_units,
            AVG(revenue) AS avg_revenue
        FROM base
        GROUP BY item_id, store_id
    )
    SELECT *
    FROM agg
    ORDER BY promo_weeks DESC, avg_discount_pct ASC
    LIMIT {limit}
    """

    df = pd.read_sql(query, engine)

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "item_id": r["item_id"],
            "store_id": r["store_id"],
            "total_weeks": int(r["total_weeks"]),
            "promo_weeks": int(r["promo_weeks"]),
            "avg_discount_pct": float(r["avg_discount_pct"]) if pd.notna(r["avg_discount_pct"]) else 0.0,
            "avg_units": float(r["avg_units"]) if pd.notna(r["avg_units"]) else 0.0,
            "avg_revenue": float(r["avg_revenue"]) if pd.notna(r["avg_revenue"]) else 0.0,
        })

    return {"rows": rows}