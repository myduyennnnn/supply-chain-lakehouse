{{ config(materialized='view') }}

SELECT *
FROM read_parquet(
    's3://supply-chain-ai-native/bronze/clickstream/**/*.parquet',
    hive_partitioning = true
)