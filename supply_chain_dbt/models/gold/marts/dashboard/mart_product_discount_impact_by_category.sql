{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_product_discount_impact_by_category.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Product Discount Impact by Category (DIAGNOSTIC)
-- Grain: 1 row per (category_name, discount_bucket)
-- Usage: Tab "Product" - diagnose category nào nhạy cảm nhất với
--        discount (sales tăng/giảm mạnh khi discount tăng)
-- Source: fact_order_items + dim_product
-- ============================================================

WITH base AS (
    SELECT
        p.category_name,
        f.order_item_discount_rate,
        f.sales,
        CASE
            WHEN f.order_item_discount_rate = 0      THEN '0%'
            WHEN f.order_item_discount_rate <= 0.10  THEN '1-10%'
            WHEN f.order_item_discount_rate <= 0.20  THEN '11-20%'
            WHEN f.order_item_discount_rate <= 0.30  THEN '21-30%'
            ELSE '31%+'
        END AS discount_bucket
    FROM {{ ref('fact_order_items') }} f
    LEFT JOIN {{ ref('dim_product') }} p
        ON f.product_card_id = p.product_card_id
)

SELECT
    category_name,
    discount_bucket,
    COUNT(*)     AS order_item_count,
    AVG(sales)   AS avg_sales
FROM base
GROUP BY
    category_name,
    discount_bucket