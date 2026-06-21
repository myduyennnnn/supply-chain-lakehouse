{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/dimensions/dim_date.parquet',
    format='parquet'
) }}

WITH date_spine AS (
    SELECT CAST(d AS DATE) AS date_day
    FROM (
        SELECT UNNEST(GENERATE_SERIES(
            (SELECT MIN(order_date) FROM {{ ref('stg_order') }}),
            (SELECT MAX(shipping_date) FROM {{ ref('stg_order') }}),
            INTERVAL '1 day'
        )) AS d
    )
)

SELECT
    CAST(strftime(date_day, '%Y%m%d') AS INTEGER) AS date_key,
    date_day,
    EXTRACT(year FROM date_day)    AS year,
    EXTRACT(quarter FROM date_day) AS quarter,
    EXTRACT(month FROM date_day)   AS month,
    strftime(date_day, '%B')       AS month_name,
    EXTRACT(day FROM date_day)     AS day_of_month,
    EXTRACT(dow FROM date_day)     AS day_of_week,
    strftime(date_day, '%A')       AS day_name,
    EXTRACT(week FROM date_day)    AS week_of_year
FROM date_spine