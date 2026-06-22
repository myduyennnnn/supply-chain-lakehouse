{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/facts/fact_order_items.parquet',
    format='parquet'
) }}

SELECT
    oi.order_item_id,                                       -- degenerate dimension
    oi.order_id,                                            -- FK → dim_order
    oi.product_card_id,                                     -- FK → dim_product
    o.customer_id,                                          -- FK → dim_customer
    CAST(strftime('%Y%m%d', o.order_date)    AS INTEGER) AS order_date_key,     -- FK → dim_date (role-playing)
    CAST(strftime('%Y%m%d', o.shipping_date) AS INTEGER) AS shipping_date_key,  -- FK → dim_date (role-playing)

    oi.order_item_quantity,
    oi.order_item_product_price,
    oi.order_item_discount_amount,
    oi.order_item_discount_rate,
    oi.sales,
    oi.order_item_total,
    oi.order_item_profit_ratio,
    oi.order_profit
FROM {{ ref('stg_order_items') }} oi
LEFT JOIN {{ ref('stg_order') }} o
    ON oi.order_id = o.order_id