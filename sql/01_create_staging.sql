-- QuickCommerce Ops Tower — staging views over warehouse / local SQL tables
-- Works with DuckDB, Postgres, or a warehouse SQL endpoint
-- Grain notes live in excel/01_data_dictionary.xlsx

-- stg_orders: typed order header
CREATE OR REPLACE VIEW stg.orders AS
SELECT
    order_id,
    store_id,
    metro,
    zone,
    CAST(ordered_at AS TIMESTAMP) AS ordered_at,
    CAST(order_date AS DATE) AS order_date,
    hour,
    slot,
    weather,
    promo_type,
    status,
    cancel_reason,
    rider_id,
    promise_minutes,
    o2d_minutes,
    sla_hit,
    gmv,
    discount_amount,
    delivery_fee,
    net_gmv,
    cogs,
    lines_ordered,
    lines_fulfilled,
    had_stockout,
    CASE WHEN status IN ('Delivered', 'Partial') THEN 1 ELSE 0 END AS is_delivered,
    CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END AS is_cancelled
FROM landing.orders_raw;

CREATE OR REPLACE VIEW stg.order_lines AS
SELECT
    order_id,
    sku_id,
    qty_ordered,
    qty_fulfilled,
    unit_price,
    line_gmv,
    line_discount,
    line_cost,
    stockout_flag
FROM landing.order_lines_raw;

CREATE OR REPLACE VIEW stg.stores AS
SELECT store_id, store_name, metro, zone, city_tier, promise_minutes, store_capacity_orders_hr
FROM landing.dim_stores_raw;

CREATE OR REPLACE VIEW stg.skus AS
SELECT sku_id, sku_name, category, mrp, unit_cost, perishable, shelf_life_days
FROM landing.dim_skus_raw;

CREATE OR REPLACE VIEW stg.riders AS
SELECT rider_id, store_id, shift, vehicle, active
FROM landing.dim_riders_raw;

CREATE OR REPLACE VIEW stg.stockouts AS
SELECT event_id, order_id, store_id, sku_id, CAST(event_ts AS TIMESTAMP) AS event_ts, reason
FROM landing.stockout_events_raw;
