{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_ai_monitoring_summary.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: AI Monitoring Summary
-- Grain: 1 row (single-row KPI summary)
-- Usage: Tab "AI Monitoring" - Predicted Late / Actual Late / Violations
-- Source: dim_order
-- ============================================================

SELECT
    SUM(CASE WHEN late_delivery_risk THEN 1 ELSE 0 END)  AS predicted_late,
    SUM(CASE WHEN is_actual_late THEN 1 ELSE 0 END)      AS actual_late,
    SUM(CASE WHEN is_label_violation THEN 1 ELSE 0 END)  AS violations
FROM {{ ref('dim_order') }}