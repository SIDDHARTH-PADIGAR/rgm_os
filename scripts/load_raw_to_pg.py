"""
Load raw Instacart CSV files into PostgreSQL raw tables.

What this script does:
1. Connects to PostgreSQL
2. Executes schema.sql to create the schema/tables
3. Reads raw CSV files from data/raw/
4. Loads them into rgm.raw_* tables

Run:
python -m scripts.load_raw_to_pg
"""

from pathlib import Path
import pandas as pd
from sqlalchemy import text
from app.db import engine

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"

CSV_TABLE_MAP = {
    "orders.csv": "raw_orders",
    "order_products__prior.csv": "raw_order_products_prior",
    "order_products__train.csv": "raw_order_products_train",
    "products.csv": "raw_products",
    "aisles.csv": "raw_aisles",
    "departments.csv": "raw_departments",
}


def create_schema():
    """Run schema.sql to create all warehouse tables."""
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql = f.read()

    # Split on semicolons so we can execute statements one by one
    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def load_csv_to_table(csv_path: Path, table_name: str):
    """
    Read a CSV file and append it into rgm.<table_name>.
    Using pandas to_sql for simplicity in V1.
    """
    print(f"Loading {csv_path.name} -> rgm.{table_name}")

    df = pd.read_csv(csv_path)

    # Append to the target table inside schema rgm
    df.to_sql(
        name=table_name,
        con=engine,
        schema="rgm",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=50000
    )

    print(f"Finished loading {csv_path.name}. Rows: {len(df):,}")


def main():
    create_schema()

    for filename, table_name in CSV_TABLE_MAP.items():
        csv_path = RAW_DIR / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing file: {csv_path}")
        load_csv_to_table(csv_path, table_name)

    print("All raw files loaded successfully.")


if __name__ == "__main__":
    main()