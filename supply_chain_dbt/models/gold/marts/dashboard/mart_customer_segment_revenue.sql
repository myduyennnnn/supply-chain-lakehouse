{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_customer_segment_revenue.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Customer Segment Revenue (DIAGNOSTIC)
-- Grain: 1 row per customer_segment
-- Usage: Tab "Customer" - diagnose segment nào thực sự đóng góp
--        sales/profit nhiều nhất (mart_customer_summary cũ chỉ đếm
--        số customer, không nối với revenue)
-- Source: fact_order_items + dim_customer
-- ============================================================

SELECT
    c.customer_segment,
    COUNT(DISTINCT f.customer_id)                                       AS total_customers,
    SUM(f.sales)                                                        AS total_sales,
    SUM(f.order_profit)                                                 AS total_profit,
    ROUND(SUM(f.sales) / NULLIF(COUNT(DISTINCT f.customer_id), 0), 2)   AS avg_revenue_per_customer
FROM {{ ref('fact_order_items') }} f
LEFT JOIN {{ ref('dim_customer') }} c
    ON f.customer_id = c.customer_id
GROUP BY
    c.customer_segment