{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_supply_chain_region_delay.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Supply Chain Region Delay
-- Grain: 1 row per order_region
-- Usage: Tab "Supply Chain" - Average Delay by Region
-- Source: dim_order
-- ============================================================

SELECT
    order_region,
    AVG(days_diff) AS avg_delay
FROM {{ ref('dim_order') }}
GROUP BY
    order_region