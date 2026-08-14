-- Analytics marts — same logic as python/01_clean_ops_tables.py
-- Publish as warehouse tables or views for the Power BI semantic model

CREATE OR REPLACE TABLE marts.fact_orders AS
SELECT
    o.*,
    (o.net_gmv - o.cogs) AS gross_margin,
    CAST(strftime(o.order_date, '%Y%m%d') AS INT) AS date_key  -- Spark: date_format
FROM stg.orders o;

CREATE OR REPLACE TABLE marts.mart_daily AS
SELECT
    order_date,
    COUNT(*) AS orders,
    SUM(is_delivered) AS delivered_orders,
    SUM(is_cancelled) AS cancelled_orders,
    SUM(gmv) AS gmv,
    SUM(net_gmv) AS net_gmv,
    SUM(discount_amount) AS discount_amount,
    SUM(sla_hit) AS sla_hits,
    SUM(had_stockout) AS stockout_orders,
    SUM(gmv) * 1.0 / NULLIF(SUM(is_delivered), 0) AS aov,
    SUM(sla_hit) * 1.0 / NULLIF(SUM(is_delivered), 0) AS sla_hit_pct,
    SUM(is_cancelled) * 1.0 / COUNT(*) AS cancel_pct,
    SUM(had_stockout) * 1.0 / COUNT(*) AS stockout_rate
FROM marts.fact_orders
GROUP BY order_date;

-- Store scorecard
CREATE OR REPLACE TABLE marts.mart_store AS
SELECT
    store_id,
    metro,
    zone,
    COUNT(*) AS orders,
    SUM(is_delivered) AS delivered_orders,
    SUM(is_cancelled) AS cancelled_orders,
    SUM(gmv) AS gmv,
    SUM(net_gmv) AS net_gmv,
    SUM(sla_hit) AS sla_hits,
    SUM(had_stockout) AS stockout_orders,
    SUM(sla_hit) * 1.0 / NULLIF(SUM(is_delivered), 0) AS sla_hit_pct,
    SUM(is_cancelled) * 1.0 / COUNT(*) AS cancel_pct,
    SUM(had_stockout) * 1.0 / COUNT(*) AS stockout_rate,
    SUM(gmv) * 1.0 / NULLIF(SUM(is_delivered), 0) AS aov
    -- O2D percentiles: use APPROX_PERCENTILE in Spark / warehouse SQL
FROM marts.fact_orders
GROUP BY store_id, metro, zone;

CREATE OR REPLACE TABLE marts.mart_zone AS
SELECT
    metro,
    zone,
    COUNT(*) AS orders,
    SUM(gmv) AS gmv,
    AVG(sla_hit * 1.0) AS sla_hit_pct,
    AVG(is_cancelled * 1.0) AS cancel_pct,
    AVG(had_stockout * 1.0) AS stockout_rate
FROM marts.fact_orders
GROUP BY metro, zone;

CREATE OR REPLACE TABLE marts.mart_promo AS
SELECT
    promo_type,
    COUNT(*) AS orders,
    SUM(is_delivered) AS delivered,
    SUM(gmv) AS gmv,
    SUM(discount_amount) AS discount_amount,
    SUM(net_gmv) AS net_gmv,
    AVG(is_cancelled * 1.0) AS cancel_pct,
    SUM(discount_amount) * 1.0 / NULLIF(SUM(gmv), 0) AS promo_burn_pct
FROM marts.fact_orders
GROUP BY promo_type;

-- Top stockout SKUs
CREATE OR REPLACE TABLE marts.mart_top_stockout_skus AS
SELECT
    s.sku_id,
    k.sku_name,
    k.category,
    COUNT(*) AS stockout_events
FROM stg.stockouts s
JOIN stg.skus k ON k.sku_id = s.sku_id
GROUP BY s.sku_id, k.sku_name, k.category
ORDER BY stockout_events DESC;
