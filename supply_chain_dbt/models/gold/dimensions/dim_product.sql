{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/dimensions/dim_product.parquet',
    format='parquet'
) }}

SELECT
    p.product_card_id,
    p.product_name,
    p.product_price,
    p.product_status,
    p.product_status_label,
    p.category_id,
    p.category_name,
    p.department_id,
    d.department_name
FROM {{ ref('stg_product') }} p
LEFT JOIN {{ ref('stg_department') }} d
    ON p.department_id = d.department_id