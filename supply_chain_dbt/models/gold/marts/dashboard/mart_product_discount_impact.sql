{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_product_discount_impact.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Product Discount Impact
-- Grain: 1 row per order_item_discount_rate
-- Usage: Tab "Product" - Discount Impact on Sales (scatter)
-- Source: fact_order_items
-- ============================================================

SELECT
    order_item_discount_rate,
    AVG(sales) AS avg_sales
FROM {{ ref('fact_order_items') }}
GROUP BY
    order_item_discount_rate