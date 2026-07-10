"""
Build rgm.fact_sales_weekly entirely in PostgreSQL from raw M5 tables.
"""

from sqlalchemy import text
from app.db import engine

SQL = """
DROP TABLE IF EXISTS rgm.fact_sales_weekly;

CREATE TABLE rgm.fact_sales_weekly AS
WITH daily_enriched AS (
    SELECT
        s.item_id,
        s.dept_id,
        s.cat_id,
        s.store_id,
        s.state_id,
        c.wm_yr_wk,
        c.date,
        s.units_sold,
        c.event_name_1,
        c.event_type_1,
        c.event_name_2,
        c.event_type_2,
        CASE
            WHEN s.state_id = 'CA' THEN c.snap_ca
            WHEN s.state_id = 'TX' THEN c.snap_tx
            ELSE c.snap_wi
        END AS snap_flag
    FROM rgm.raw_m5_sales_daily s
    INNER JOIN rgm.raw_m5_calendar c
        ON s.d = c.d
),
weekly_sales AS (
    SELECT
        item_id,
        dept_id,
        cat_id,
        store_id,
        state_id,
        wm_yr_wk,
        MIN(date) AS week_start_date,
        SUM(units_sold) AS units_sold,
        MAX(event_name_1) AS event_name_1,
        MAX(event_type_1) AS event_type_1,
        MAX(event_name_2) AS event_name_2,
        MAX(event_type_2) AS event_type_2,
        MAX(snap_flag) AS snap_flag
    FROM daily_enriched
    GROUP BY item_id, dept_id, cat_id, store_id, state_id, wm_yr_wk
)
SELECT
    w.item_id,
    w.dept_id,
    w.cat_id,
    w.store_id,
    w.state_id,
    w.wm_yr_wk,
    w.week_start_date,
    w.units_sold,
    p.sell_price,
    (w.units_sold * p.sell_price) AS revenue,
    w.event_name_1,
    w.event_type_1,
    w.event_name_2,
    w.event_type_2,
    w.snap_flag
FROM weekly_sales w
LEFT JOIN rgm.raw_m5_prices p
    ON w.store_id = p.store_id
   AND w.item_id = p.item_id
   AND w.wm_yr_wk = p.wm_yr_wk;
"""

def main():
    print("Building rgm.fact_sales_weekly in PostgreSQL...")
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print("Done building rgm.fact_sales_weekly.")


if __name__ == "__main__":
    main()