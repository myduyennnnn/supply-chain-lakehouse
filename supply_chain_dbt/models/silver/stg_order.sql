{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/silver/order/stg_order.parquet',
    format='parquet'
) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_orders') }}
),

cleaned AS (
    SELECT
        CAST("Order Id" AS INTEGER)                             AS order_id,
        CAST("Order Customer Id" AS INTEGER)                    AS customer_id,
        TRIM("Type")                                            AS payment_type,

        TRIM("Order Status")                                    AS order_status,
        TRIM("Market")                                          AS market,
        TRIM("Order Region")                                    AS order_region,
        TRIM("Order Country")                                   AS order_country,
        TRIM("Order State")                                     AS order_state,
        TRIM("Order City")                                      AS order_city,
        CAST("Latitude" AS DOUBLE)              AS delivery_latitude,
        CAST("Longitude" AS DOUBLE)             AS delivery_longitude,

        STRPTIME("order date (DateOrders)", '%m/%d/%Y %H:%M')   AS order_date,
        STRPTIME("shipping date (DateOrders)", '%m/%d/%Y %H:%M') AS shipping_date,
        TRIM("Shipping Mode")                                   AS shipping_mode,
        TRIM("Delivery Status")                                 AS delivery_status,
        
        CAST("Days for shipment (scheduled)" AS INTEGER)        AS days_scheduled,
        CAST("Days for shipping (real)" AS INTEGER)             AS days_actual,

        -- Label Noise
        CAST("Days for shipping (real)" AS INTEGER) 
            - CAST("Days for shipment (scheduled)" AS INTEGER)  AS days_diff,

        CAST("Late_delivery_risk" AS BOOLEAN)                   AS late_delivery_risk,

        CASE 
            WHEN CAST("Days for shipping (real)" AS INTEGER) > CAST("Days for shipment (scheduled)" AS INTEGER) THEN 1
            ELSE 0
        END AS is_actual_late,

        CASE 
            WHEN CAST("Days for shipping (real)" AS INTEGER) > CAST("Days for shipment (scheduled)" AS INTEGER) 
                 AND CAST("Late_delivery_risk" AS INTEGER) = 0 THEN TRUE 
            ELSE FALSE 
        END AS is_label_violation,

        CURRENT_TIMESTAMP AS _loaded_at,
        _ingested_at

    FROM source
    WHERE "Order Id" IS NOT NULL
),

final AS (
    SELECT * EXCLUDE (_ingested_at)
    FROM cleaned
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY order_id
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM final