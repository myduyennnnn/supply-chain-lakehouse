"""
Upload Utilities

Chức năng:
- Upload CSV lên Cloudflare R2
- Upload Parquet lên Cloudflare R2
- Hỗ trợ Multipart Upload cho file lớn
- Tự động chọn phương thức upload phù hợp

Sử dụng cho Bronze Layer của Data Lakehouse.
"""

import io
import math
import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ==========================================================
# Upload Configuration
# ==========================================================

# Nếu file lớn hơn 50MB -> dùng Multipart Upload
MULTIPART_THRESHOLD = 50 * 1024 * 1024

# Kích thước mỗi part
CHUNK_SIZE = 10 * 1024 * 1024


# ==========================================================
# Low-Level Upload Functions
# ==========================================================

def _upload_simple(
    client,
    bucket: str,
    data: bytes,
    key: str,
    content_type: str,
) -> None:
    """
    Upload file bằng PUT Object.

    Phù hợp:
        File nhỏ (< 50MB)
    """

    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def _upload_multipart(
    client,
    bucket: str,
    data: bytes,
    key: str,
    content_type: str,
) -> None:
    """
    Multipart Upload.

    Phù hợp:
        File lớn (> 50MB)

    Cloudflare R2 hỗ trợ giao thức S3 Multipart Upload.
    """

    total_size = len(data)

    num_parts = math.ceil(
        total_size / CHUNK_SIZE
    )

    logger.info(
        "Multipart Upload: %s parts",
        num_parts,
    )

    multipart = client.create_multipart_upload(
        Bucket=bucket,
        Key=key,
        ContentType=content_type,
    )

    upload_id = multipart["UploadId"]

    parts = []

    try:

        for i in range(num_parts):

            part_number = i + 1

            start = i * CHUNK_SIZE

            end = min(
                start + CHUNK_SIZE,
                total_size,
            )

            chunk = data[start:end]

            response = client.upload_part(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=chunk,
            )

            parts.append(
                {
                    "PartNumber": part_number,
                    "ETag": response["ETag"],
                }
            )

            logger.info(
                "Part %s/%s uploaded (%.2f MB)",
                part_number,
                num_parts,
                len(chunk) / 1024 / 1024,
            )

        client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={
                "Parts": parts
            },
        )

    except Exception:

        logger.exception(
            "Multipart upload failed. Aborting..."
        )

        client.abort_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
        )

        raise


# ==========================================================
# Smart Upload
# ==========================================================

def smart_upload(
    client,
    bucket: str,
    data: bytes,
    key: str,
    content_type: str,
    label: str,
) -> None:
    """
    Tự động chọn:
        - PUT Object
        - Multipart Upload

    dựa trên kích thước file.
    """

    size_mb = len(data) / 1024 / 1024

    logger.info(
        "Preparing %s upload (%.2f MB)",
        label,
        size_mb,
    )

    if len(data) > MULTIPART_THRESHOLD:

        _upload_multipart(
            client=client,
            bucket=bucket,
            data=data,
            key=key,
            content_type=content_type,
        )

    else:

        _upload_simple(
            client=client,
            bucket=bucket,
            data=data,
            key=key,
            content_type=content_type,
        )

    logger.info(
        "Upload successful → s3://%s/%s",
        bucket,
        key,
    )


# ==========================================================
# DataFrame Upload Helpers
# ==========================================================

def upload_csv(
    client,
    bucket: str,
    df: pd.DataFrame,
    key: str,
) -> None:
    """
    DataFrame → CSV → Upload.
    """

    buffer = io.StringIO()

    df.to_csv(
        buffer,
        index=False,
        encoding="utf-8",
    )

    smart_upload(
        client=client,
        bucket=bucket,
        data=buffer.getvalue().encode("utf-8"),
        key=key,
        content_type="text/csv",
        label="CSV",
    )


def upload_parquet(
    client,
    bucket: str,
    df: pd.DataFrame,
    key: str,
) -> None:
    """
    DataFrame → Parquet(Snappy) → Upload.
    """

    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        index=False,
        engine="pyarrow",
        compression="snappy",
    )

    buffer.seek(0)

    smart_upload(
        client=client,
        bucket=bucket,
        data=buffer.getvalue(),
        key=key,
        content_type="application/octet-stream",
        label="PARQUET",
    )