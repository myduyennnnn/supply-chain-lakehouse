{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_ai_monitoring_risk_by_region.parquet',
    format='parquet'
) }}

SELECT
    order_region,
    SUM(CASE WHEN late_delivery_risk THEN 1 ELSE 0 END) AS risk_orders
FROM {{ ref('dim_order') }}
GROUP BY order_region
