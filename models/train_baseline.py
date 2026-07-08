"""
Train the baseline demand forecasting model.

Goal:
Predict product-week units_sold using lagged demand and simple metadata.

Model:
LightGBMRegressor

Why baseline only right now?
Because promo incrementality and elasticity depend on having a reasonable
baseline demand layer first.

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


def load_feature_table() -> pd.DataFrame:
    query = "SELECT * FROM rgm.feature_product_weekly"
    return pd.read_sql(query, engine)


def train_test_split_time(df: pd.DataFrame):
    """
    Time-based split:
    - earlier weeks -> train
    - latest 20% of weeks -> test

    We split by week_id, not random row split, because this is a forecasting problem.
    """
    unique_weeks = sorted(df["week_id"].unique())
    cutoff_idx = int(len(unique_weeks) * 0.8)
    train_weeks = unique_weeks[:cutoff_idx]
    test_weeks = unique_weeks[cutoff_idx:]

    train_df = df[df["week_id"].isin(train_weeks)].copy()
    test_df = df[df["week_id"].isin(test_weeks)].copy()

    return train_df, test_df


def prepare_xy(df: pd.DataFrame):
    """
    Select model features and target.

    For V1 we keep it simple and only use features that exist in the real data.
    """
    feature_cols = [
        "product_id",
        "department_id",
        "aisle_id",
        "order_count",
        "reorder_units",
        "avg_add_to_cart_order",
        "avg_days_since_prior_order",
        "lag_1_units",
        "lag_2_units",
        "lag_4_units",
        "rolling_4w_mean",
        "rolling_4w_std",
    ]

    X = df[feature_cols].copy()
    y = df["units_sold"].copy()
    return X, y, feature_cols


def main():
    df = load_feature_table()
    print(f"Feature rows loaded: {len(df):,}")

    train_df, test_df = train_test_split_time(df)

    X_train, y_train, feature_cols = prepare_xy(train_df)
    X_test, y_test, _ = prepare_xy(test_df)

    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=31,
        random_state=42
    )

    print("Training baseline model...")
    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    mae = mean_absolute_error(y_test, preds)
    rmse = mean_squared_error(y_test, preds) ** 0.5

    print(f"Baseline model MAE:  {mae:.4f}")
    print(f"Baseline model RMSE: {rmse:.4f}")

    artifact = {
        "model": model,
        "feature_cols": feature_cols,
        "metrics": {
            "mae": mae,
            "rmse": rmse
        }
    }

    out_path = ARTIFACT_DIR / "baseline_model.joblib"
    joblib.dump(artifact, out_path)

    print(f"Saved model artifact to: {out_path}")


if __name__ == "__main__":
    main()