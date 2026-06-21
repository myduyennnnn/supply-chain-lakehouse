{{ config(materialized='table') }}

WITH order_customer AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.days_actual,
        o.days_scheduled,
        o.late_delivery_risk,
        o.order_country,
        c.customer_segment,
        c.customer_country
    FROM {{ ref('stg_order') }} o
    LEFT JOIN {{ ref('stg_customer') }} c ON o.customer_id = c.customer_id
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
