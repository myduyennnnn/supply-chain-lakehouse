{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/silver/customer/stg_customer.parquet',
    format='parquet'
) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_orders') }}
),

cleaned AS (
    SELECT
        CAST("Customer Id" AS INTEGER)                                          AS customer_id,

        TRIM("Customer Fname")                                                  AS customer_first_name,
        COALESCE(TRIM("Customer Lname"), '')                                    AS customer_last_name,
        TRIM(TRIM("Customer Fname") || ' ' || COALESCE(TRIM("Customer Lname"), ''))
                                                                                AS customer_full_name,
        TRIM("Customer Segment")                                                AS customer_segment,

        TRIM("Customer City")                                                   AS customer_city,
        TRIM("Customer State")                                                  AS customer_state,
        TRIM("Customer Country")                                                AS customer_country,
        TRIM("Customer Street")                                                 AS customer_street,
        
        CASE 
            WHEN "Customer Zipcode" IS NULL OR TRIM(CAST("Customer Zipcode" AS VARCHAR)) = '' THEN 'Unknown'
            ELSE TRIM(CAST("Customer Zipcode" AS VARCHAR))
        END                                                                     AS customer_zipcode,

        CURRENT_TIMESTAMP AS _loaded_at,
        _ingested_at

    FROM source
    WHERE "Customer Id" IS NOT NULL
),

final AS (
    SELECT * EXCLUDE (_ingested_at)
    FROM cleaned
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM final