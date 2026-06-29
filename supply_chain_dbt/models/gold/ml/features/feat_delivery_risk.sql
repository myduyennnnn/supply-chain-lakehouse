{{ config(materialized='table') }}

WITH raw_joined AS (
    SELECT
        oi.*,
        o.* EXCLUDE (
            order_id, order_status, delivery_status, days_actual,
            days_diff, is_actual_late, is_label_violation,
            delivery_latitude, delivery_longitude
        ),
        p.category_name,
        p.department_name,
        c.customer_segment,
        c.customer_country
    FROM {{ ref('fact_order_items') }} oi
    INNER JOIN {{ ref('dim_order') }} o ON oi.order_id = o.order_id
    LEFT JOIN {{ ref('dim_product') }} p ON oi.product_card_id = p.product_card_id
    LEFT JOIN {{ ref('dim_customer') }} c ON oi.customer_id = c.customer_id
)

SELECT
    * EXCLUDE (
        order_id, order_item_id, product_card_id, customer_id,
        order_date_key, shipping_date_key, order_date, shipping_date
    ),
    
    CAST(ISODOW(order_date) IN (6, 7) AS INT) AS is_weekend,
    MONTH(order_date) AS order_month,
    QUARTER(order_date) AS order_quarter,
    ISODOW(shipping_date) AS ship_day_of_week,
    EXTRACT(HOUR FROM order_date) AS order_hour,
    CAST(EXTRACT(HOUR FROM order_date) >= 18 OR EXTRACT(HOUR FROM order_date) < 6 AS INT) AS is_night_order,

    CAST(customer_country != order_country AS INT) AS is_cross_border,

    order_profit / NULLIF(sales, 0) AS profit_margin,
    sales / NULLIF(order_item_quantity, 0) AS unit_price,
    CAST(days_scheduled <= 2 AS INT) AS is_urgent_shipping,
    CAST(order_item_discount_rate > 0.15 AS INT) AS is_high_discount

FROM raw_joined