from pathlib import Path
import sys

# Thêm thư mục gốc project vào PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from ingestion.clients.duckdb_client import get_duckdb_connection

con = get_duckdb_connection()

df = con.execute("""
SELECT *
FROM read_parquet(
's3://supply-chain-ai-native/bronze/orders/DataCoSupplyChainDataset.parquet'
)
LIMIT 5
""").fetchdf()

print(df)

result = con.execute("""
SELECT COUNT(*) as total_rows
FROM read_parquet(
's3://supply-chain-ai-native/bronze/orders/DataCoSupplyChainDataset.parquet'
)
""").fetchdf()

print(result)