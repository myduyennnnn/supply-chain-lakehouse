{{ config(materialized='table') }}

-- ============================================================
-- Model: feat_delivery_risk
-- Grain: 1 row per order item
-- Mục đích: feature table ML-ready cho bài toán dự đoán
--           late_delivery_risk. Khác với phiên bản trước,
--           các cột leakage (chỉ biết được SAU khi giao hàng)
--           bị loại bỏ ngay tại tầng SQL, không còn phụ thuộc
--           vào train_model.py để tự drop thủ công.
-- ============================================================

WITH raw_joined AS (
    SELECT
        oi.*,
        o.* EXCLUDE (
            order_id,           -- ID, không phải feature
            order_status,       -- chỉ biết sau khi giao (leakage)
            delivery_status,    -- chỉ biết sau khi giao (leakage)
            days_actual,        -- chỉ biết sau khi giao (leakage)
            days_diff,          -- chỉ biết sau khi giao (leakage)
            is_actual_late,     -- = target dạng khác (leakage)
            is_label_violation, -- label-noise flag, không phải feature
            delivery_latitude,  -- toạ độ giao hàng, nhiễu địa lý
            delivery_longitude  -- toạ độ giao hàng, nhiễu địa lý
        ),
        p.category_name,
        p.department_name,
        c.customer_segment,
        c.customer_country

    FROM {{ ref('fact_order_items') }}  oi
    INNER JOIN {{ ref('dim_order') }}    o ON oi.order_id        = o.order_id
    LEFT JOIN  {{ ref('dim_product') }}  p ON oi.product_card_id = p.product_card_id
    LEFT JOIN  {{ ref('dim_customer') }} c ON oi.customer_id     = c.customer_id
)

SELECT
    * EXCLUDE (
        order_id,            -- ID, không phải feature
        order_item_id,       -- ID, không phải feature
        product_card_id,     -- ID, không phải feature
        customer_id,         -- ID + PII
        order_date_key,      -- raw date key, đã engineer thành feature bên dưới
        shipping_date_key,   -- raw date key, đã engineer thành feature bên dưới
        order_date,          -- raw date, đã engineer thành feature bên dưới
        shipping_date        -- raw date, đã engineer thành feature bên dưới
    ),

    -- ── Derived temporal features ───────────────────────────
    CASE
        WHEN (ISODOW(order_date) - 1) >= 5 THEN 1
        ELSE 0
    END                                       AS is_weekend,
    MONTH(order_date)                         AS order_month,
    QUARTER(order_date)                       AS order_quarter,
    (ISODOW(shipping_date) - 1)               AS ship_day_of_week,

    -- ── Derived business features ───────────────────────────
    order_profit / NULLIF(sales, 0)                    AS profit_margin,
    sales / NULLIF(order_item_quantity, 0)              AS unit_price,
    CASE
        WHEN days_scheduled <= 2 THEN 1
        ELSE 0
    END                                       AS is_urgent_shipping

FROM raw_joined