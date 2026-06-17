{{ config(
    materialized='external',
    location='s3://supply-chain-ai-native/silver/department/stg_department.parquet',
    format='parquet'
) }}

WITH source AS (
    SELECT * FROM {{ source('bronze_orders', 'raw_orders') }}
),

cleaned AS (
    SELECT
        CAST("Department Id" AS INTEGER)            AS department_id,
        TRIM("Department Name")                     AS department_name,

        _ingested_at

    FROM source
    WHERE "Department Id" IS NOT NULL
),

final AS (
    SELECT * EXCLUDE (_ingested_at)
    FROM cleaned
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY department_id
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM final