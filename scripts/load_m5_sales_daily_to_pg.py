"""
Load M5 daily sales into PostgreSQL in chunked long format.

Source:
data/raw/m5/sales_train_validation.csv

Target:
rgm.raw_m5_sales_daily

Why this exists:
The full M5 sales file is wide and huge. Melting it all at once blows up RAM.
So we process it chunk-by-chunk:
- read N item rows
- melt d_* columns into long daily rows
- append to PostgreSQL
- repeat
"""

from pathlib import Path
import pandas as pd
from sqlalchemy import text
from app.db import engine

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw" / "m5"
SALES_PATH = RAW_DIR / "sales_train_validation.csv"

ID_COLS = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
CHUNK_SIZE = 500  # tune up later if your machine handles more


def reset_target_table():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE rgm.raw_m5_sales_daily;"))


def main():
    print("Resetting rgm.raw_m5_sales_daily...")
    reset_target_table()

    print(f"Reading {SALES_PATH.name} in chunks of {CHUNK_SIZE} rows...")
    total_rows_written = 0
    chunk_num = 0

    for chunk in pd.read_csv(SALES_PATH, chunksize=CHUNK_SIZE):
        chunk_num += 1
        print(f"\nProcessing chunk {chunk_num} with {len(chunk):,} item rows...")

        day_cols = [c for c in chunk.columns if c.startswith("d_")]

        long_chunk = chunk.melt(
            id_vars=ID_COLS,
            value_vars=day_cols,
            var_name="d",
            value_name="units_sold"
        )

        # Optional: downcast units to int16-ish if you want, but not necessary now
        long_chunk.to_sql(
            "raw_m5_sales_daily",
            engine,
            schema="rgm",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=50000
        )

        total_rows_written += len(long_chunk)
        print(f"Chunk {chunk_num} written. Long rows appended: {len(long_chunk):,}")
        print(f"Total long rows written so far: {total_rows_written:,}")

    print("\nDone loading rgm.raw_m5_sales_daily.")
    print(f"Final long rows written: {total_rows_written:,}")


if __name__ == "__main__":
    main()