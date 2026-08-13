-- Quality checks I run before publishing cleaned tables to marts
-- Expectation: all queries return 0 rows (or the documented exception)

-- 1) Duplicate order headers
SELECT order_id, COUNT(*) AS n
FROM stg.orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 2) Negative money fields (should be empty)
SELECT order_id, gmv, net_gmv, discount_amount
FROM stg.orders
WHERE gmv < 0 OR net_gmv < 0 OR discount_amount < 0;

-- 3) Delivered orders missing O2D
SELECT order_id, status, o2d_minutes
FROM stg.orders
WHERE status IN ('Delivered', 'Partial')
  AND o2d_minutes IS NULL;

-- 4) Cancelled orders that still carry GMV (should be empty on this extract)
SELECT order_id, status, gmv
FROM stg.orders
WHERE status = 'Cancelled' AND gmv > 0;

-- 5) Orphan lines (no header)
SELECT l.order_id, COUNT(*) AS lines
FROM stg.order_lines l
LEFT JOIN stg.orders o ON o.order_id = l.order_id
WHERE o.order_id IS NULL
GROUP BY l.order_id;

-- 6) SLA flag inconsistent with promise clock
-- (allowing tiny float noise — flag only clear mismatches)
SELECT order_id, o2d_minutes, promise_minutes, sla_hit
FROM stg.orders
WHERE status IN ('Delivered', 'Partial')
  AND (
        (o2d_minutes <= promise_minutes AND sla_hit = 0)
     OR (o2d_minutes > promise_minutes AND sla_hit = 1)
  );

-- 7) Stockout events without a matching order
SELECT s.event_id, s.order_id
FROM stg.stockouts s
LEFT JOIN stg.orders o ON o.order_id = s.order_id
WHERE o.order_id IS NULL;

-- 8) Rider assigned on cancelled order (should be empty)
SELECT order_id, status, rider_id
FROM stg.orders
WHERE status = 'Cancelled' AND rider_id IS NOT NULL;
