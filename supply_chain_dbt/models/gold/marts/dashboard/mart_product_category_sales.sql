{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_product_category_sales.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Product Category Sales
-- Grain: 1 row per category_name
-- Usage: Tab "Product" - Top Categories
-- Source: fact_order_items + dim_product
-- ============================================================

SELECT
    p.category_name,
    SUM(f.sales) AS total_sales
FROM {{ ref('fact_order_items') }} f
LEFT JOIN {{ ref('dim_product') }} p
    ON f.product_card_id = p.product_card_id
GROUP BY
    p.category_name