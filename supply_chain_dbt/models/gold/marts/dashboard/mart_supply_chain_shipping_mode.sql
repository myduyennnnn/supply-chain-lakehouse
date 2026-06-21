{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_supply_chain_shipping_mode.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Supply Chain Shipping Mode
-- Grain: 1 row per shipping_mode
-- Usage: Tab "Supply Chain" - Shipping Mode Distribution
-- Source: dim_order
-- ============================================================

SELECT
    shipping_mode,
    COUNT(*) AS total_orders
FROM {{ ref('dim_order') }}
GROUP BY
    shipping_mode