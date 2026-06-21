{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_executive_summary.parquet',
    format='parquet'
) }}

WITH base AS (
    SELECT
        f.order_id,
        f.product_card_id,
        f.sales,
        f.order_profit,
        o.order_region,
        p.department_name
    FROM {{ ref('fact_order_items') }} f
    LEFT JOIN {{ ref('dim_order') }} o
        ON f.order_id = o.order_id
    LEFT JOIN {{ ref('dim_product') }} p
        ON f.product_card_id = p.product_card_id
)

SELECT
    order_region,
    department_name,
    COUNT(DISTINCT order_id)   AS total_orders,
    SUM(sales)                 AS total_sales,
    SUM(order_profit)          AS total_profit,
    ROUND(SUM(order_profit) / NULLIF(SUM(sales), 0) * 100, 2) AS profit_margin_pct  -- diagnostic: combo region x department nào đang lỗ
FROM base
GROUP BY
    order_region,
    department_name