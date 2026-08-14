-- KPI pack — numbers must match reports/kpi_summary.json
-- Run against marts.fact_orders (or the CSV-backed semantic model)

-- Headline ops KPIs (delivered = Delivered + Partial)
SELECT
    COUNT(*) AS orders,
    SUM(is_delivered) AS delivered_orders,
    SUM(is_cancelled) AS cancelled_orders,
    ROUND(SUM(CASE WHEN is_delivered = 1 THEN gmv ELSE 0 END), 2) AS gmv_inr,
    ROUND(
        SUM(CASE WHEN is_delivered = 1 THEN gmv ELSE 0 END)
        / NULLIF(SUM(is_delivered), 0),
        2
    ) AS aov_inr,
    ROUND(AVG(CASE WHEN is_delivered = 1 THEN sla_hit END), 4) AS sla_hit_pct,
    ROUND(AVG(had_stockout * 1.0), 4) AS stockout_rate,
    ROUND(AVG(is_cancelled * 1.0), 4) AS cancel_pct,
    ROUND(SUM(CASE WHEN is_delivered = 1 THEN discount_amount ELSE 0 END), 2) AS promo_burn_inr
FROM marts.fact_orders;

-- O2D percentiles on delivered only
-- Spark / warehouse:
--   approx_percentile(o2d_minutes, 0.5), approx_percentile(o2d_minutes, 0.9)
SELECT
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o2d_minutes), 2) AS o2d_p50_min,
    ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY o2d_minutes), 2) AS o2d_p90_min
FROM marts.fact_orders
WHERE is_delivered = 1 AND o2d_minutes IS NOT NULL;

-- Worst SLA zones
SELECT metro, zone,
       ROUND(AVG(sla_hit * 1.0), 4) AS sla_hit_pct,
       ROUND(AVG(had_stockout * 1.0), 4) AS stockout_rate,
       COUNT(*) AS orders
FROM marts.fact_orders
GROUP BY metro, zone
ORDER BY sla_hit_pct ASC
LIMIT 5;

-- Promo burn vs GMV
SELECT promo_type,
       COUNT(*) AS orders,
       ROUND(SUM(gmv), 0) AS gmv,
       ROUND(SUM(discount_amount), 0) AS discount_amount,
       ROUND(SUM(discount_amount) * 1.0 / NULLIF(SUM(gmv), 0), 4) AS burn_pct
FROM marts.fact_orders
WHERE is_delivered = 1
GROUP BY promo_type
ORDER BY discount_amount DESC;

-- Cancel reasons
SELECT cancel_reason, COUNT(*) AS cancels
FROM marts.fact_orders
WHERE is_cancelled = 1
GROUP BY cancel_reason
ORDER BY cancels DESC;
