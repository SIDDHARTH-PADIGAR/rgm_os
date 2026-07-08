"""
Build the baseline feature store for the Revenue Growth Management OS.

This version avoids a single giant join+groupby that can crash local Postgres.
Instead it works in stages:

1. Build indexes in SQL if needed
2. Create a lighter intermediate join table: order_features_prior
3. Aggregate that table to product-week base
4. Pull the aggregated base into pandas
5. Add lag / rolling features
6. Save final feature table back to PostgreSQL
"""

import pandas as pd
from sqlalchemy import text
from app.db import engine


def create_indexes():
    """
    Create indexes to make joins/grouping faster.
    Safe to rerun because of IF NOT EXISTS.
    """
    sql = """
    CREATE INDEX IF NOT EXISTS idx_raw_orders_order_id
        ON rgm.raw_orders(order_id);

    CREATE INDEX IF NOT EXISTS idx_raw_orders_eval_set
        ON rgm.raw_orders(eval_set);

    CREATE INDEX IF NOT EXISTS idx_raw_orders_order_number
        ON rgm.raw_orders(order_number);

    CREATE INDEX IF NOT EXISTS idx_raw_order_products_prior_order_id
        ON rgm.raw_order_products_prior(order_id);

    CREATE INDEX IF NOT EXISTS idx_raw_order_products_prior_product_id
        ON rgm.raw_order_products_prior(product_id);

    CREATE INDEX IF NOT EXISTS idx_raw_products_product_id
        ON rgm.raw_products(product_id);
    """
    with engine.begin() as conn:
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            conn.execute(text(stmt))


def build_order_features_prior():
    """
    Build a lighter intermediate table by joining orders and prior order lines only.

    This avoids repeating the huge raw join every time and lets us aggregate from
    a narrower table.
    """
    sql = """
    DROP TABLE IF EXISTS rgm.order_features_prior;

    CREATE TABLE rgm.order_features_prior AS
    SELECT
        o.order_id,
        ((o.order_number - 1) / 4)::int AS week_id,
        o.days_since_prior_order,
        op.product_id,
        op.add_to_cart_order,
        op.reordered
    FROM rgm.raw_orders o
    INNER JOIN rgm.raw_order_products_prior op
        ON o.order_id = op.order_id
    WHERE o.eval_set = 'prior';
    """
    with engine.begin() as conn:
        conn.execute(text(sql))


def build_product_week_base():
    """
    Aggregate the lighter intermediate table into product-week grain,
    joining product metadata only at this stage.
    """
    sql = """
    DROP TABLE IF EXISTS rgm.product_week_base;

    CREATE TABLE rgm.product_week_base AS
    SELECT
        f.week_id,
        f.product_id,
        p.department_id,
        p.aisle_id,
        COUNT(*) AS units_sold,
        SUM(f.reordered) AS reorder_units,
        COUNT(DISTINCT f.order_id) AS order_count,
        AVG(f.add_to_cart_order::float) AS avg_add_to_cart_order,
        AVG(f.days_since_prior_order) AS avg_days_since_prior_order
    FROM rgm.order_features_prior f
    INNER JOIN rgm.raw_products p
        ON f.product_id = p.product_id
    GROUP BY
        f.week_id,
        f.product_id,
        p.department_id,
        p.aisle_id;
    """
    with engine.begin() as conn:
        conn.execute(text(sql))


def load_product_week_base() -> pd.DataFrame:
    """
    Load the already-aggregated product-week base table from PostgreSQL.
    """
    return pd.read_sql("SELECT * FROM rgm.product_week_base", engine)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add lag and rolling features per product.
    """
    df = df.sort_values(["product_id", "week_id"]).copy()
    grouped = df.groupby("product_id")

    df["lag_1_units"] = grouped["units_sold"].shift(1)
    df["lag_2_units"] = grouped["units_sold"].shift(2)
    df["lag_4_units"] = grouped["units_sold"].shift(4)

    df["rolling_4w_mean"] = (
        grouped["units_sold"]
        .shift(1)
        .rolling(4, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )

    df["rolling_4w_std"] = (
        grouped["units_sold"]
        .shift(1)
        .rolling(4, min_periods=1)
        .std()
        .reset_index(level=0, drop=True)
    )

    df["rolling_4w_std"] = df["rolling_4w_std"].fillna(0)

    # Need at least one lag to train
    df = df[df["lag_1_units"].notna()].copy()
    return df


def save_feature_table(df: pd.DataFrame):
    """
    Save final feature table to PostgreSQL.
    """
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS rgm.feature_product_weekly;")

    df.to_sql(
        name="feature_product_weekly",
        con=engine,
        schema="rgm",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=50000
    )


def main():
    print("Step 1/4: Creating indexes...")
    create_indexes()
    print("Indexes ready.")

    print("Step 2/4: Building rgm.order_features_prior...")
    build_order_features_prior()
    print("Built rgm.order_features_prior")

    print("Step 3/4: Building rgm.product_week_base...")
    build_product_week_base()
    print("Built rgm.product_week_base")

    print("Step 4/4: Loading aggregated data and creating lag features...")
    df = load_product_week_base()
    print(f"Loaded rows from product_week_base: {len(df):,}")

    feature_df = add_time_features(df)
    print(f"Rows after lag feature generation: {len(feature_df):,}")

    print("Saving final feature table to PostgreSQL...")
    save_feature_table(feature_df)

    print("Feature store build complete.")
    print(feature_df.head())


if __name__ == "__main__":
    main()