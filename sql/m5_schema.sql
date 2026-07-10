CREATE SCHEMA IF NOT EXISTS rgm;

DROP TABLE IF EXISTS rgm.raw_m5_calendar;
CREATE TABLE rgm.raw_m5_calendar (
    date DATE,
    wm_yr_wk INT,
    weekday TEXT,
    wday INT,
    month INT,
    year INT,
    d TEXT,
    event_name_1 TEXT,
    event_type_1 TEXT,
    event_name_2 TEXT,
    event_type_2 TEXT,
    snap_ca INT,
    snap_tx INT,
    snap_wi INT
);

DROP TABLE IF EXISTS rgm.raw_m5_prices;
CREATE TABLE rgm.raw_m5_prices (
    store_id TEXT,
    item_id TEXT,
    wm_yr_wk INT,
    sell_price NUMERIC
);

DROP TABLE IF EXISTS rgm.raw_m5_sales_meta;
CREATE TABLE rgm.raw_m5_sales_meta (
    id TEXT,
    item_id TEXT,
    dept_id TEXT,
    cat_id TEXT,
    store_id TEXT,
    state_id TEXT
);

DROP TABLE IF EXISTS rgm.raw_m5_sales_daily;
CREATE TABLE rgm.raw_m5_sales_daily (
    id TEXT,
    item_id TEXT,
    dept_id TEXT,
    cat_id TEXT,
    store_id TEXT,
    state_id TEXT,
    d TEXT,
    units_sold NUMERIC
);

DROP TABLE IF EXISTS rgm.fact_sales_weekly;
CREATE TABLE rgm.fact_sales_weekly (
    item_id TEXT,
    dept_id TEXT,
    cat_id TEXT,
    store_id TEXT,
    state_id TEXT,
    wm_yr_wk INT,
    week_start_date DATE,
    units_sold NUMERIC,
    sell_price NUMERIC,
    revenue NUMERIC,
    event_name_1 TEXT,
    event_type_1 TEXT,
    event_name_2 TEXT,
    event_type_2 TEXT,
    snap_flag INT
);

DROP TABLE IF EXISTS rgm.feature_rgm_weekly;
CREATE TABLE rgm.feature_rgm_weekly (
    item_id TEXT,
    dept_id TEXT,
    cat_id TEXT,
    store_id TEXT,
    state_id TEXT,
    wm_yr_wk INT,
    week_start_date DATE,

    units_sold NUMERIC,
    sell_price NUMERIC,
    revenue NUMERIC,

    event_name_1 TEXT,
    event_type_1 TEXT,
    event_name_2 TEXT,
    event_type_2 TEXT,
    snap_flag INT,

    lag_1_units NUMERIC,
    lag_2_units NUMERIC,
    lag_4_units NUMERIC,
    rolling_4w_mean NUMERIC,
    rolling_4w_std NUMERIC,

    lag_1_price NUMERIC,
    price_change_pct_1w NUMERIC,
    rolling_4w_price_mean NUMERIC,

    week_of_month INT,
    month INT,
    year INT,
    is_event_week INT
);