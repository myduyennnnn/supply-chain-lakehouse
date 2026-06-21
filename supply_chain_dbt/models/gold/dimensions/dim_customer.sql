{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/dimensions/dim_customer.parquet',
    format='parquet'
) }}

SELECT
    customer_id,
    customer_first_name,
    customer_last_name,
    customer_full_name,
    customer_segment,
    customer_city,
    customer_state,
    customer_country,
    customer_street,
    customer_zipcode
FROM {{ ref('stg_customer') }}