"""
Dataset configuration

Mapping:
    Local CSV file
        ↓
    Bronze zone in R2
"""

INGEST_CONFIG = {
    "DataCoSupplyChainDataset.csv": {
        "bronze_prefix": "bronze/orders",
        "dataset_name": "orders",
        "encoding": "latin-1",
        "description": "Supply Chain Orders Dataset",
        "skip_parquet": False,
    },

    "tokenized_access_logs.csv": {
        "bronze_prefix": "bronze/clickstream",
        "dataset_name": "clickstream",
        "encoding": "utf-8",
        "description": "Clickstream Dataset",
        "skip_parquet": False,
    },

    "DescriptionDataCoSupplyChain.csv": {
        "bronze_prefix": "bronze/orders",
        "dataset_name": "metadata",
        "encoding": "utf-8",
        "description": "Data Dictionary",
        "skip_parquet": True,
    },
}