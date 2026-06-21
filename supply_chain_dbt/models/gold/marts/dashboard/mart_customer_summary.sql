{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_customer_summary.parquet',
    format='parquet'
) }}


SELECT
    customer_segment,
    customer_country,
    COUNT(DISTINCT customer_id) AS total_customers
FROM {{ ref('dim_customer') }}
GROUP BY
    customer_segment,
    customer_country