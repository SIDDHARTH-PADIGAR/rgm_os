"""
Load raw M5 files into PostgreSQL.

This script loads:
- calendar.csv -> rgm.raw_m5_calendar
- sell_prices.csv -> rgm.raw_m5_prices
- sales_train_validation.csv metadata columns only -> rgm.raw_m5_sales_meta

The daily sales long table is loaded separately by:
python -m scripts.load_m5_sales_daily_to_pg
"""

from pathlib import Path
import pandas as pd
from sqlalchemy import text
from app.db import engine

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw" / "m5"
SQL_PATH = BASE_DIR / "sql" / "m5_schema.sql"


def run_schema():
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    with engine.begin() as conn:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            conn.execute(text(stmt))


def truncate_base_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE rgm.raw_m5_calendar;"))
        conn.execute(text("TRUNCATE TABLE rgm.raw_m5_prices;"))
        conn.execute(text("TRUNCATE TABLE rgm.raw_m5_sales_meta;"))


def load_calendar():
    path = RAW_DIR / "calendar.csv"
    print(f"Loading {path.name} -> rgm.raw_m5_calendar")

    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # Normalize M5 SNAP columns to lowercase to match Postgres schema
    df = df.rename(columns={
        "snap_CA": "snap_ca",
        "snap_TX": "snap_tx",
        "snap_WI": "snap_wi",
    })

    df.to_sql(
        "raw_m5_calendar",
        engine,
        schema="rgm",
        if_exists="append",
        index=False
    )

    print(f"Finished {path.name}. Rows: {len(df):,}")


def load_prices():
    path = RAW_DIR / "sell_prices.csv"
    print(f"Loading {path.name} -> rgm.raw_m5_prices")

    df = pd.read_csv(path)

    df.to_sql(
        "raw_m5_prices",
        engine,
        schema="rgm",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=10000
    )

    print(f"Finished {path.name}. Rows: {len(df):,}")


def load_sales_meta():
    path = RAW_DIR / "sales_train_validation.csv"
    print(f"Loading metadata slice of {path.name} -> rgm.raw_m5_sales_meta")

    df = pd.read_csv(
        path,
        usecols=["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    )

    df.to_sql(
        "raw_m5_sales_meta",
        engine,
        schema="rgm",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=10000
    )

    print(f"Finished metadata slice. Rows: {len(df):,}")


def main():
    print("Running schema setup...")
    run_schema()
    print("Schema ready.")

    print("Clearing base raw tables...")
    truncate_base_tables()

    load_calendar()
    load_prices()
    load_sales_meta()

    print("Raw calendar / prices / sales metadata loaded successfully.")


if __name__ == "__main__":
    main()