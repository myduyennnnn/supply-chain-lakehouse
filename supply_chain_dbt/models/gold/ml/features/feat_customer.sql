{{ config(materialized='table') }}

WITH order_level AS (
    SELECT DISTINCT
        oi.customer_id,
        oi.order_id,
        o.days_actual,
        o.days_scheduled,
        o.late_delivery_risk,
        o.order_country
    FROM {{ ref('fact_order_items') }} oi
    LEFT JOIN {{ ref('dim_order') }}   o  ON oi.order_id = o.order_id
),

order_customer AS (
    SELECT
        ol.order_id,
        ol.customer_id,
        ol.days_actual,
        ol.days_scheduled,
        ol.late_delivery_risk,
        ol.order_country,
        c.customer_segment,
        c.customer_country
    FROM order_level                  ol
    LEFT JOIN {{ ref('dim_customer') }} c ON ol.customer_id = c.customer_id
),

final AS (
    SELECT
        customer_id,
        customer_segment,
        customer_country,

        COUNT(DISTINCT order_id)                                            AS total_orders,

        ROUND(AVG(days_actual - days_scheduled), 3)                        AS avg_days_late,

        ROUND(
            SUM(CASE WHEN late_delivery_risk THEN 1 ELSE 0 END)::DOUBLE
            / NULLIF(COUNT(*), 0),
        3)                                                                  AS late_delivery_rate,

        MAX(CASE WHEN customer_country != order_country THEN 1 ELSE 0 END) AS is_cross_border

    FROM order_customer
    GROUP BY customer_id, customer_segment, customer_country
)

SELECT * FROM final
