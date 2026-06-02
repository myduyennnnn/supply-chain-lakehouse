import os
from dotenv import load_dotenv
import duckdb

load_dotenv()

con = duckdb.connect()

con.execute("""
INSTALL httpfs;
LOAD httpfs;
""")

con.execute(f"""
SET s3_access_key_id='{os.getenv("R2_ACCESS_KEY_ID")}';
""")

con.execute(f"""
SET s3_secret_access_key='{os.getenv("R2_SECRET_ACCESS_KEY")}';
""")

con.execute("""
SET s3_endpoint='e49eaef183d28c29671eb8fa90aeb624.r2.cloudflarestorage.com';
""")

con.execute("""
SET s3_url_style='path';
""")

con.execute("""
SET s3_use_ssl=true;
""")

print("Connected to R2")

df = con.execute("""
SELECT *
FROM read_parquet(
's3://supply-chain-ai-native/bronze/orders/DataCoSupplyChainDataset.parquet'
)
LIMIT 5
""").df()

print(df)