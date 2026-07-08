-- =========================================================
-- Revenue Growth Management OS
-- Initial warehouse schema for Instacart-based V1
-- =========================================================

CREATE SCHEMA IF NOT EXISTS rgm;

-- ---------------------------------------------------------
-- RAW TABLES
-- ---------------------------------------------------------

DROP TABLE IF EXISTS rgm.raw_orders;
CREATE TABLE rgm.raw_orders (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT,
    eval_set TEXT,
    order_number INT,
    order_dow INT,
    order_hour_of_day INT,
    days_since_prior_order FLOAT
);

DROP TABLE IF EXISTS rgm.raw_order_products_prior;
CREATE TABLE rgm.raw_order_products_prior (
    order_id BIGINT,
    product_id BIGINT,
    add_to_cart_order INT,
    reordered INT
);

DROP TABLE IF EXISTS rgm.raw_order_products_train;
CREATE TABLE rgm.raw_order_products_train (
    order_id BIGINT,
    product_id BIGINT,
    add_to_cart_order INT,
    reordered INT
);

DROP TABLE IF EXISTS rgm.raw_products;
CREATE TABLE rgm.raw_products (
    product_id BIGINT PRIMARY KEY,
    product_name TEXT,
    aisle_id INT,
    department_id INT
);

DROP TABLE IF EXISTS rgm.raw_aisles;
CREATE TABLE rgm.raw_aisles (
    aisle_id INT PRIMARY KEY,
    aisle TEXT
);

DROP TABLE IF EXISTS rgm.raw_departments;
CREATE TABLE rgm.raw_departments (
    department_id INT PRIMARY KEY,
    department TEXT
);

-- ---------------------------------------------------------
-- FEATURE TABLE
-- Product-week grain for baseline demand modeling
-- ---------------------------------------------------------

DROP TABLE IF EXISTS rgm.feature_product_weekly;
CREATE TABLE rgm.feature_product_weekly (
    week_id INT,
    product_id BIGINT,
    department_id INT,
    aisle_id INT,

    units_sold BIGINT,
    reorder_units BIGINT,
    order_count BIGINT,
    avg_add_to_cart_order FLOAT,
    avg_days_since_prior_order FLOAT,

    lag_1_units FLOAT,
    lag_2_units FLOAT,
    lag_4_units FLOAT,
    rolling_4w_mean FLOAT,
    rolling_4w_std FLOAT,

    PRIMARY KEY (week_id, product_id)
);