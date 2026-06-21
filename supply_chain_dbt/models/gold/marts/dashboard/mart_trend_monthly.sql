{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/gold/marts/dashboard/mart_trend_monthly.parquet',
    format='parquet'
) }}

-- ============================================================
-- Mart: Monthly Trend (DIAGNOSTIC)
-- Grain: 1 row per (year, month)
-- Usage: Tab "Executive" / "Supply Chain" - diagnose biến động
--        sales/profit/delay theo thời gian (trước giờ dim_date
--        chưa được mart nào dùng tới)
-- Source: fact_order_items + dim_date + dim_order
--
-- LƯU Ý: avg_delay được tính riêng ở grain order (dedup order_id
-- trước khi AVG), KHÔNG tính trực tiếp trên base order-item — vì
-- days_diff là thuộc tính cấp order, nếu AVG trên base order-item
-- thì order nào nhiều line item sẽ bị weighted nặng hơn, làm lệch
-- so với avg_delay của mart_supply_chain_region_delay.
-- ============================================================

WITH base AS (
    SELECT
        f.order_id,
        f.sales,
        f.order_profit,
        d.year,
        d.month,
        d.month_name
    FROM {{ ref('fact_order_items') }} f
    LEFT JOIN {{ ref('dim_date') }} d
        ON f.order_date_key = d.date_key
),

sales_monthly AS (
    SELECT
        year,
        month,
        month_name,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(sales)               AS total_sales,
        SUM(order_profit)        AS total_profit
    FROM base
    GROUP BY
        year,
        month,
        month_name
),

order_month AS (
    -- 1 dòng duy nhất per order_id, để AVG(days_diff) không bị nhân theo số order item
    SELECT DISTINCT
        b.order_id,
        b.year,
        b.month,
        b.month_name,
        o.days_diff
    FROM base b
    LEFT JOIN {{ ref('dim_order') }} o
        ON b.order_id = o.order_id
),

delay_monthly AS (
    SELECT
        year,
        month,
        month_name,
        AVG(days_diff) AS avg_delay
    FROM order_month
    GROUP BY
        year,
        month,
        month_name
)

SELECT
    s.year,
    s.month,
    s.month_name,
    s.total_orders,
    s.total_sales,
    s.total_profit,
    d.avg_delay
FROM sales_monthly s
LEFT JOIN delay_monthly d
    ON s.year = d.year
   AND s.month = d.month
   AND s.month_name = d.month_name
ORDER BY
    s.year,
    s.month