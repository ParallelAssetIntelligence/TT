"""Upload Excel files to Supabase Storage.

Two buckets:
  - uploaded-leads:  raw files Matt drops in chat, staged for enrichment
  - enriched-files:  outputs we hand back to Matt as download links

Bucket setup (one-time, do this in Supabase dashboard):
  - Public: yes
  - File size limit: 50 MB
"""
import os
import logging
import re
from datetime import datetime
from supabase import create_client

logger = logging.getLogger(__name__)

ENRICHED_BUCKET = "enriched-files"
UPLOADED_BUCKET = "uploaded-leads"
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload_enriched_file(file_bytes: bytes, original_filename: str = "leads.xlsx") -> str:
    """Upload enriched Excel to Supabase Storage. Returns public download URL."""
    return _upload_to_bucket(ENRICHED_BUCKET, file_bytes, original_filename)


def upload_uploaded_file(file_bytes: bytes, original_filename: str = "leads.xlsx") -> tuple[str, str]:
    """Stage a raw uploaded Excel in the uploaded-leads bucket.

    Returns (storage_path, public_url). The path is what we'll hand to the
    enrichment job; the URL is what we surface to Matt for confirmation.
    """
    return _upload_to_bucket(UPLOADED_BUCKET, file_bytes, original_filename, return_path=True)


def _upload_to_bucket(bucket: str, file_bytes: bytes, original_filename: str, return_path: bool = False):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing — set SUPABASE_URL and SUPABASE_KEY")

    client = create_client(url, key)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_filename(original_filename)
    storage_path = f"{timestamp}_{safe_name}"

    try:
        client.storage.from_(bucket).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": EXCEL_MIME,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
    except Exception as e:
        logger.error(f"Supabase upload to {bucket} failed: {e}")
        raise RuntimeError(f"Storage upload failed: {e}") from e

    public_url = client.storage.from_(bucket).get_public_url(storage_path)
    logger.info(f"Uploaded {bucket}/{storage_path} → {public_url}")
    return (storage_path, public_url) if return_path else public_url


def _safe_filename(name: str) -> str:
    """Strip path separators and weird chars so the storage key is well-formed."""
    base = os.path.basename(name.strip()) or "leads.xlsx"
    if not base.lower().endswith((".xlsx", ".xls")):
        base = f"{base}.xlsx"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)
