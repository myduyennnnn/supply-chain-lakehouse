-- Doanh thu theo tháng
SELECT
    DATE_TRUNC('month', o.order_date)   AS month,
    SUM(oi.sales)                       AS total_sales,
    SUM(oi.order_profit_per_order)      AS total_profit,
    COUNT(DISTINCT o.order_id)          AS total_orders
FROM read_parquet('s3://supply-chain-ai-native/silver/order_items/stg_order_items.parquet') oi
LEFT JOIN read_parquet('s3://supply-chain-ai-native/silver/order/stg_order.parquet') o
    ON oi.order_id = o.order_id
GROUP BY 1
ORDER BY 1