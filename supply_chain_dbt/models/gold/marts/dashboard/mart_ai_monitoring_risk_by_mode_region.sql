{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_ai_monitoring_risk_by_mode_region.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: AI Monitoring Risk by Shipping Mode x Region (DIAGNOSTIC)
-- Grain: 1 row per (order_region, shipping_mode)
-- Usage: Tab "AI Monitoring" - diagnose risk/violations tập trung ở
--        combo region x shipping_mode nào, thay vì chỉ xem theo region
-- Source: dim_order
-- ============================================================

SELECT
    order_region,
    shipping_mode,
    COUNT(*)                                                AS total_orders,
    SUM(CASE WHEN late_delivery_risk THEN 1 ELSE 0 END)     AS predicted_late,
    SUM(CASE WHEN is_actual_late THEN 1 ELSE 0 END)         AS actual_late,
    SUM(CASE WHEN is_label_violation THEN 1 ELSE 0 END)     AS violations
FROM {{ ref('dim_order') }}
GROUP BY
    order_region,
    shipping_mode