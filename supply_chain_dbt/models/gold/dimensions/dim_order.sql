{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/dimensions/dim_order.parquet',
    format='parquet'
) }}

SELECT
    order_id,
    payment_type,
    order_status,
    market,
    order_region,
    order_country,
    order_state,
    order_city,
    delivery_latitude,
    delivery_longitude,
    order_date,
    shipping_date,
    shipping_mode,
    delivery_status,
    days_scheduled,
    days_actual,
    days_diff,
    late_delivery_risk,
    is_actual_late,
    is_label_violation
FROM {{ ref('stg_order') }}