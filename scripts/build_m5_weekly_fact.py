"""
Build weekly fact table for RGM from M5 data.

Output grain:
one row = item_id x store_id x wm_yr_wk

This script:
1. Reads sales_train_validation.csv in wide format
2. Melts daily d_* columns into long form
3. Joins calendar to map each d_* to wm_yr_wk and date
4. Aggregates daily sales to week
5. Joins weekly sell price
6. Joins event / SNAP context
7. Saves rgm.fact_sales_weekly
"""

from pathlib import Path
import numpy as np
import pandas as pd
from app.db import engine

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw" / "m5"


def load_raw_files():
    sales = pd.read_csv(RAW_DIR / "sales_train_validation.csv")
    cal = pd.read_csv(RAW_DIR / "calendar.csv")
    prices = pd.read_csv(RAW_DIR / "sell_prices.csv")

    cal["date"] = pd.to_datetime(cal["date"])
    return sales, cal, prices


def melt_sales_long(sales: pd.DataFrame) -> pd.DataFrame:
    id_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    day_cols = [c for c in sales.columns if c.startswith("d_")]

    sales_long = sales.melt(
        id_vars=id_cols,
        value_vars=day_cols,
        var_name="d",
        value_name="units_sold"
    )

    return sales_long


def build_weekly_fact(
    sales_long: pd.DataFrame,
    cal: pd.DataFrame,
    prices: pd.DataFrame
) -> pd.DataFrame:
    # join day -> calendar info
    df = sales_long.merge(
        cal[
            [
                "d",
                "date",
                "wm_yr_wk",
                "month",
                "year",
                "event_name_1",
                "event_type_1",
                "event_name_2",
                "event_type_2",
                "snap_CA",
                "snap_TX",
                "snap_WI",
            ]
        ],
        on="d",
        how="left"
    )

    # state-specific SNAP flag
    df["snap_flag"] = np.where(
        df["state_id"] == "CA",
        df["snap_CA"],
        np.where(df["state_id"] == "TX", df["snap_TX"], df["snap_WI"])
    )

    # aggregate daily sales to item-store-week
    weekly = (
        df.groupby(
            ["item_id", "dept_id", "cat_id", "store_id", "state_id", "wm_yr_wk"],
            as_index=False
        )
        .agg(
            units_sold=("units_sold", "sum"),
            week_start_date=("date", "min"),
            event_name_1=("event_name_1", "first"),
            event_type_1=("event_type_1", "first"),
            event_name_2=("event_name_2", "first"),
            event_type_2=("event_type_2", "first"),
            snap_flag=("snap_flag", "max")
        )
    )

    # join weekly sell price
    weekly = weekly.merge(
        prices,
        on=["store_id", "item_id", "wm_yr_wk"],
        how="left"
    )

    # revenue proxy
    weekly["revenue"] = weekly["units_sold"] * weekly["sell_price"]

    return weekly


def save_weekly_fact(df: pd.DataFrame):
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS rgm.fact_sales_weekly;")

    df.to_sql(
        "fact_sales_weekly",
        engine,
        schema="rgm",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=50000
    )


def main():
    print("Loading raw M5 files...")
    sales, cal, prices = load_raw_files()

    print("Melting daily sales into long format...")
    sales_long = melt_sales_long(sales)
    print(f"Long sales rows: {len(sales_long):,}")

    print("Building weekly fact table...")
    weekly = build_weekly_fact(sales_long, cal, prices)
    print(f"Weekly fact rows: {len(weekly):,}")

    print("Saving rgm.fact_sales_weekly...")
    save_weekly_fact(weekly)

    print("Done building fact_sales_weekly.")
    print(weekly.head())


if __name__ == "__main__":
    main()