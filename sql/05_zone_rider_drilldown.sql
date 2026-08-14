-- Practice joins / drilldowns I used while wiring the report pages

-- Store × slot SLA (evening rush check)
SELECT
    o.store_id,
    o.zone,
    o.slot,
    COUNT(*) AS orders,
    ROUND(AVG(o.sla_hit * 1.0), 3) AS sla_hit_pct,
    ROUND(AVG(o.o2d_minutes), 2) AS avg_o2d
FROM marts.fact_orders o
WHERE o.is_delivered = 1
GROUP BY o.store_id, o.zone, o.slot
ORDER BY sla_hit_pct ASC
LIMIT 20;

-- Rider scorecard joined to home store
SELECT
    r.rider_id,
    r.store_id,
    s.zone,
    r.vehicle,
    COUNT(*) AS deliveries,
    ROUND(AVG(o.o2d_minutes), 2) AS avg_o2d,
    ROUND(AVG(o.sla_hit * 1.0), 3) AS sla_hit_pct
FROM marts.fact_orders o
JOIN stg.riders r ON r.rider_id = o.rider_id
JOIN stg.stores s ON s.store_id = r.store_id
WHERE o.is_delivered = 1
GROUP BY r.rider_id, r.store_id, s.zone, r.vehicle
HAVING COUNT(*) >= 50
ORDER BY sla_hit_pct ASC
LIMIT 25;

-- Weather impact on O2D
SELECT
    weather,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(o2d_minutes), 2) AS avg_o2d,
    ROUND(AVG(sla_hit * 1.0), 3) AS sla_hit_pct,
    ROUND(AVG(is_cancelled * 1.0), 3) AS cancel_pct
FROM marts.fact_orders
GROUP BY weather
ORDER BY avg_o2d DESC;
