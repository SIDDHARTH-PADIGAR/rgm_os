"""
KPI summary service for Revenue Growth OS.

Purpose:
Return top-line metrics from rgm.fact_sales_weekly for the dashboard header.

Metrics:
- total revenue
- total units sold
- avg weekly revenue
- avg weekly units
- number of unique SKUs
- number of unique stores
"""

import pandas as pd
from app.db import engine


def get_kpi_summary():
    query = """
    WITH weekly AS (
        SELECT
            wm_yr_wk,
            SUM(revenue) AS weekly_revenue,
            SUM(units_sold) AS weekly_units
        FROM rgm.fact_sales_weekly
        GROUP BY wm_yr_wk
    )
    SELECT
        (SELECT SUM(revenue) FROM rgm.fact_sales_weekly) AS total_revenue,
        (SELECT SUM(units_sold) FROM rgm.fact_sales_weekly) AS total_units,
        (SELECT AVG(weekly_revenue) FROM weekly) AS avg_weekly_revenue,
        (SELECT AVG(weekly_units) FROM weekly) AS avg_weekly_units,
        (SELECT COUNT(DISTINCT item_id) FROM rgm.fact_sales_weekly) AS unique_items,
        (SELECT COUNT(DISTINCT store_id) FROM rgm.fact_sales_weekly) AS unique_stores
    """
    df = pd.read_sql(query, engine)
    row = df.iloc[0].to_dict()

    # cast numpy types into normal Python types for JSON safety
    return {
        "total_revenue": float(row["total_revenue"] or 0),
        "total_units": float(row["total_units"] or 0),
        "avg_weekly_revenue": float(row["avg_weekly_revenue"] or 0),
        "avg_weekly_units": float(row["avg_weekly_units"] or 0),
        "unique_items": int(row["unique_items"] or 0),
        "unique_stores": int(row["unique_stores"] or 0),
    }