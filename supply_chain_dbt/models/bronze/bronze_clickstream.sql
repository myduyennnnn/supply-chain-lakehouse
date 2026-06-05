{{ config(materialized='view') }}

SELECT *
FROM read_parquet(
    's3://supply-chain-ai-native/bronze/clickstream/tokenized_access_logs.parquet'
)