"""
Build RGM feature table in PostgreSQL.

Output:
rgm.feature_rgm_weekly

Grain:
one row = item_id x store_id x wm_yr_wk

Adds:
- lag demand features
- lag price features
- rolling demand features
- promo / discount features
- historical item-store price bounds for scenario guardrails
"""

from sqlalchemy import text
from app.db import engine


SQL = """
DROP TABLE IF EXISTS rgm.feature_rgm_weekly;

CREATE TABLE rgm.feature_rgm_weekly AS
WITH base AS (
    SELECT
        item_id,
        dept_id,
        cat_id,
        store_id,
        state_id,
        wm_yr_wk,
        week_start_date,
        units_sold,
        sell_price,
        revenue,
        event_name_1,
        event_type_1,
        event_name_2,
        event_type_2,
        snap_flag,

        LAG(units_sold, 1) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
        ) AS lag_1_units,

        LAG(units_sold, 2) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
        ) AS lag_2_units,

        LAG(units_sold, 4) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
        ) AS lag_4_units,

        AVG(units_sold) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS rolling_4w_units_mean,

        STDDEV_POP(units_sold) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS rolling_4w_units_std,

        LAG(sell_price, 1) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
        ) AS lag_1_price,

        AVG(sell_price) OVER (
            PARTITION BY item_id, store_id
            ORDER BY week_start_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS rolling_4w_price_mean,

        MIN(sell_price) OVER (
            PARTITION BY item_id, store_id
        ) AS historical_min_price,

        MAX(sell_price) OVER (
            PARTITION BY item_id, store_id
        ) AS historical_max_price

    FROM rgm.fact_sales_weekly
),

feat AS (
    SELECT
        *,
        CASE
            WHEN lag_1_price IS NULL OR lag_1_price = 0 THEN 0
            ELSE (sell_price - lag_1_price) / lag_1_price
        END AS price_change_pct_1w,

        CASE
            WHEN rolling_4w_price_mean IS NULL OR rolling_4w_price_mean = 0 THEN 0
            ELSE (sell_price - rolling_4w_price_mean) / rolling_4w_price_mean
        END AS price_vs_rolling_4w_pct,

        CASE
            WHEN rolling_4w_price_mean IS NULL OR rolling_4w_price_mean = 0 THEN 0
            WHEN sell_price < rolling_4w_price_mean THEN 1
            ELSE 0
        END AS promo_flag,

        CASE
            WHEN rolling_4w_price_mean IS NULL OR rolling_4w_price_mean = 0 THEN 0
            WHEN sell_price < rolling_4w_price_mean
                THEN (rolling_4w_price_mean - sell_price) / rolling_4w_price_mean
            ELSE 0
        END AS discount_pct
    FROM base
)

SELECT *
FROM feat
WHERE lag_1_units IS NOT NULL;
"""


def main():
    print("Building rgm.feature_rgm_weekly in PostgreSQL...")
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print("Done building rgm.feature_rgm_weekly.")


if __name__ == "__main__":
    main()