{{ config(materialized='view') }}

SELECT *
FROM read_parquet(
    's3://supply-chain-ai-native/bronze/orders/**/*.parquet',
    hive_partitioning = true
)