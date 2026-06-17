{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/silver/product/stg_product.parquet',
    format='parquet'
) }}

WITH source AS (
    SELECT * FROM {{ source('bronze_orders', 'raw_orders') }}
),

cleaned AS (
    SELECT
        CAST("Product Card Id" AS INTEGER)          AS product_card_id,

        TRIM("Product Name")                        AS product_name,
        CAST("Product Price" AS DOUBLE)             AS product_price,
        CAST("Product Status" AS INTEGER)           AS product_status,
        CASE
            WHEN CAST("Product Status" AS INTEGER) = 1 THEN 'Active'
            ELSE 'Inactive'
        END                                         AS product_status_label,

        CAST("Category Id" AS INTEGER)              AS category_id,
        TRIM("Category Name")                       AS category_name,

        CAST("Department Id" AS INTEGER)            AS department_id,

        _ingested_at

    FROM source
    WHERE "Product Card Id" IS NOT NULL
),

final AS (
    SELECT * EXCLUDE (_ingested_at)
    FROM cleaned
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY product_card_id
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM final
