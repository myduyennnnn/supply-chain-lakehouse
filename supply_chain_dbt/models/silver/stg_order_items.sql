{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/silver/order_items/stg_order_items.parquet',
    format='parquet'
) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_orders') }}
),

cleaned AS (
    SELECT
        CAST("Order Item Id" AS INTEGER)            AS order_item_id,
        CAST("Order Id" AS INTEGER)                 AS order_id,
        CAST("Order Item Cardprod Id" AS INTEGER)   AS product_card_id,
        CAST("Department Id" AS INTEGER)            AS department_id,

        CAST("Order Item Quantity" AS INTEGER)      AS order_item_quantity,
        CAST("Order Item Product Price" AS DOUBLE)  AS order_item_product_price,

        CAST("Order Item Discount" AS DOUBLE)       AS order_item_discount_amount,
        CAST("Order Item Discount Rate" AS DOUBLE)  AS order_item_discount_rate,

        CAST("Sales" AS DOUBLE)                     AS sales,
        CAST("Order Item Total" AS DOUBLE)          AS order_item_total,
        CAST("Order Item Profit Ratio" AS DOUBLE)   AS order_item_profit_ratio,
        CAST("Benefit per order" AS DOUBLE)         AS order_benefit,
        CAST("Order Profit Per Order" AS DOUBLE)    AS order_profit,

        CURRENT_TIMESTAMP                           AS _loaded_at,
        _ingested_at

    FROM source
    WHERE "Order Item Id" IS NOT NULL
),

final AS (
    SELECT * EXCLUDE (_ingested_at)
    FROM cleaned
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY order_item_id 
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM final