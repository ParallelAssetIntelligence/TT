"""Upload enriched Excel files to Supabase Storage.

When Matt drops a file in the Teams bot chat, we enrich it and need to
return a download link. Supabase Storage gives us a public URL for free.

Bucket setup (one-time, do this in Supabase dashboard):
  - Name: enriched-files
  - Public: yes
  - File size limit: 50 MB
"""
import os
import logging
import re
from datetime import datetime
from supabase import create_client

logger = logging.getLogger(__name__)

BUCKET = "enriched-files"
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload_enriched_file(file_bytes: bytes, original_filename: str = "leads.xlsx") -> str:
    """Upload enriched Excel to Supabase Storage. Returns public download URL.

    Raises RuntimeError on Supabase config issues so the calling endpoint can
    surface a clean error to the bot.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing — set SUPABASE_URL and SUPABASE_KEY")

    client = create_client(url, key)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_filename(original_filename)
    storage_path = f"{timestamp}_{safe_name}"

    try:
        client.storage.from_(BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": EXCEL_MIME,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
    except Exception as e:
        # The Supabase client raises StorageApiError when the bucket is missing
        # or when the file already exists (we use timestamps so collisions are rare).
        logger.error(f"Supabase upload failed: {e}")
        raise RuntimeError(f"Storage upload failed: {e}") from e

    public_url = client.storage.from_(BUCKET).get_public_url(storage_path)
    logger.info(f"Uploaded {storage_path} → {public_url}")
    return public_url


def _safe_filename(name: str) -> str:
    """Strip path separators and weird chars so the storage key is well-formed."""
    base = os.path.basename(name.strip()) or "leads.xlsx"
    if not base.lower().endswith((".xlsx", ".xls")):
        base = f"{base}.xlsx"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)
