"""
Memory-safe baseline training for RGM.

Why this version:
- full rgm.feature_rgm_weekly is too large to pull into pandas on a laptop
- we sample a manageable number of rows from PostgreSQL
- we still preserve time-based train/test split

Run:
python -m models.train_baseline
"""

from pathlib import Path
import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from lightgbm import LGBMRegressor
from app.db import engine

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# tune this if needed
MAX_TRAIN_ROWS = 300_000
MAX_TEST_ROWS = 80_000


def load_sampled_feature_table() -> pd.DataFrame:
    """
    Pull a bounded sample from PostgreSQL instead of loading the full table.

    Logic:
    - train set = first 80% of weeks, sampled down to MAX_TRAIN_ROWS
    - test set  = last 20% of weeks, sampled down to MAX_TEST_ROWS
    - then union both into one dataframe for downstream splitting
    """
    query = f"""
    WITH week_bounds AS (
        SELECT
            wm_yr_wk,
            DENSE_RANK() OVER (ORDER BY wm_yr_wk) AS wk_rank,
            COUNT(*) OVER () AS total_week_rows
        FROM (
            SELECT DISTINCT wm_yr_wk
            FROM rgm.feature_rgm_weekly
        ) w
    ),
    cutoff AS (
        SELECT MAX(wm_yr_wk) AS max_train_week
        FROM week_bounds
        WHERE wk_rank <= (
            SELECT FLOOR(MAX(wk_rank) * 0.8)::int
            FROM week_bounds
        )
    ),
    train_sample AS (
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
            lag_1_units,
            lag_2_units,
            lag_4_units,
            rolling_4w_units_mean,
            rolling_4w_units_std,
            lag_1_price,
            rolling_4w_price_mean,
            price_change_pct_1w,
            price_vs_rolling_4w_pct,
            promo_flag,
            discount_pct,
            snap_flag
        FROM rgm.feature_rgm_weekly
        WHERE wm_yr_wk <= (SELECT max_train_week FROM cutoff)
        ORDER BY RANDOM()
        LIMIT {MAX_TRAIN_ROWS}
    ),
    test_sample AS (
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
            lag_1_units,
            lag_2_units,
            lag_4_units,
            rolling_4w_units_mean,
            rolling_4w_units_std,
            lag_1_price,
            rolling_4w_price_mean,
            price_change_pct_1w,
            price_vs_rolling_4w_pct,
            promo_flag,
            discount_pct,
            snap_flag
        FROM rgm.feature_rgm_weekly
        WHERE wm_yr_wk > (SELECT max_train_week FROM cutoff)
        ORDER BY RANDOM()
        LIMIT {MAX_TEST_ROWS}
    )
    SELECT * FROM train_sample
    UNION ALL
    SELECT * FROM test_sample
    ORDER BY wm_yr_wk, week_start_date;
    """
    return pd.read_sql(query, engine)


def train_test_split_time(df: pd.DataFrame):
    unique_weeks = sorted(df["wm_yr_wk"].unique())
    cutoff_idx = int(len(unique_weeks) * 0.8)

    train_weeks = unique_weeks[:cutoff_idx]
    test_weeks = unique_weeks[cutoff_idx:]

    train_df = df[df["wm_yr_wk"].isin(train_weeks)].copy()
    test_df = df[df["wm_yr_wk"].isin(test_weeks)].copy()
    return train_df, test_df


def prepare_xy(df: pd.DataFrame):
    feature_cols = [
        "lag_1_units",
        "lag_2_units",
        "lag_4_units",
        "rolling_4w_units_mean",
        "rolling_4w_units_std",
        "sell_price",
        "lag_1_price",
        "rolling_4w_price_mean",
        "price_change_pct_1w",
        "price_vs_rolling_4w_pct",
        "promo_flag",
        "discount_pct",
        "snap_flag",
    ]

    X = df[feature_cols].fillna(0).copy()
    y = df["units_sold"].copy()
    return X, y, feature_cols


def evaluate_naive(test_df: pd.DataFrame):
    y_test = test_df["units_sold"]
    lag1_preds = test_df["lag_1_units"].fillna(0)

    mae = mean_absolute_error(y_test, lag1_preds)
    rmse = mean_squared_error(y_test, lag1_preds) ** 0.5

    print("-" * 60)
    print("Naive baseline: lag_1_units")
    print(f"MAE :  {mae:.4f}")
    print(f"RMSE:  {rmse:.4f}")


def main():
    print("Loading sampled feature set from PostgreSQL...")
    df = load_sampled_feature_table()
    print(f"Sampled feature rows loaded: {len(df):,}")

    train_df, test_df = train_test_split_time(df)

    print(f"Train rows: {len(train_df):,}")
    print(f"Test rows : {len(test_df):,}")
    print(f"Train weeks: {train_df['wm_yr_wk'].min()} -> {train_df['wm_yr_wk'].max()}")
    print(f"Test weeks : {test_df['wm_yr_wk'].min()} -> {test_df['wm_yr_wk'].max()}")

    evaluate_naive(test_df)

    X_train, y_train, feature_cols = prepare_xy(train_df)
    X_test, y_test, _ = prepare_xy(test_df)

    print("-" * 60)
    print("Training LightGBM baseline on sampled dataset...")

    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    mae = mean_absolute_error(y_test, preds)
    rmse = mean_squared_error(y_test, preds) ** 0.5

    print("LightGBM baseline")
    print(f"MAE :  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print("-" * 60)

    importance_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    print("Feature importances:")
    print(importance_df.to_string(index=False))

    artifact = {
        "model": model,
        "feature_cols": feature_cols,
        "metrics": {
            "mae": mae,
            "rmse": rmse
        },
        "training_note": {
            "mode": "sampled_training",
            "max_train_rows": MAX_TRAIN_ROWS,
            "max_test_rows": MAX_TEST_ROWS
        }
    }

    out_path = ARTIFACT_DIR / "baseline_model.joblib"
    joblib.dump(artifact, out_path)
    print(f"Saved baseline artifact to: {out_path}")


if __name__ == "__main__":
    main()