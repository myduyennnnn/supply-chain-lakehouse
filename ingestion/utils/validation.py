"""
Validation Utilities

Kiểm tra:
- File tồn tại
- File không rỗng
- Đúng định dạng CSV
- Kích thước file

Được sử dụng trước khi ingest vào Bronze Layer.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_file(local_path: Path) -> bool:
    """
    Validate source file trước khi ingest.

    Checks:
        1. File tồn tại
        2. File không rỗng
        3. Đúng định dạng .csv
    """

    # --------------------------------------------------
    # Check file exists
    # --------------------------------------------------
    if not local_path.exists():

        logger.error(
            "File does not exist: %s",
            local_path,
        )

        return False

    # --------------------------------------------------
    # Check file extension
    # --------------------------------------------------
    if local_path.suffix.lower() != ".csv":

        logger.error(
            "Invalid file format: %s (expected .csv)",
            local_path.name,
        )

        return False

    # --------------------------------------------------
    # Check file size
    # --------------------------------------------------
    file_size = local_path.stat().st_size

    if file_size == 0:

        logger.error(
            "Empty file: %s",
            local_path,
        )

        return False

    logger.info(
        "Validated file: %s (%.2f MB)",
        local_path.name,
        file_size / 1024 / 1024,
    )

    return True