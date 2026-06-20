"""
Cloudflare R2 upload service.

Each brand maps to its own R2 bucket (configured via env vars).
Uploads use the S3-compatible API endpoint; returned URLs point to
the per-bucket public CDN.
"""

import mimetypes
import uuid
from pathlib import PurePosixPath

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status

from app.config import settings

# Allowed MIME types for image uploads
_ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
}

# Max upload size: 10 MB
_MAX_BYTES = 10 * 1024 * 1024


def _s3_client():
    """Return a boto3 S3 client pointed at the R2 S3-compatible API."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def _bucket_for_brand(brand: str) -> str:
    """Resolve bucket name for a brand slug, raising 400 if not configured."""
    bucket = settings.r2_bucket_map.get(brand)
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No R2 bucket configured for brand '{brand}'. "
                   f"Add R2_BUCKET_{brand.upper()} to .env.",
        )
    return bucket


def _public_url(bucket: str, key: str) -> str:
    """Build the public CDN URL for an uploaded object."""
    # Public CDN is pub-<account_id>.r2.dev, separate from the S3 API endpoint
    cdn_base = f"https://pub-{settings.R2_ACCOUNT_ID}.r2.dev"
    return f"{cdn_base}/{key}"


async def upload_image(file: UploadFile, brand: str, folder: str = "products") -> str:
    """
    Upload *file* to the R2 bucket assigned to *brand*.

    Parameters
    ----------
    file   : the uploaded file from a FastAPI endpoint
    brand  : brand slug, e.g. "grabfabs", "awakynn"
    folder : sub-path inside the bucket, defaults to "products"

    Returns
    -------
    Public URL string of the uploaded image.
    """
    # --- validation ---
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. "
                   f"Allowed: {', '.join(sorted(_ALLOWED_MIME))}",
        )

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {_MAX_BYTES // (1024 * 1024)} MB.",
        )

    # --- build a unique key ---
    ext = PurePosixPath(file.filename or "upload").suffix or (
        "." + content_type.split("/")[-1]
    )
    key = f"{folder}/{uuid.uuid4().hex}{ext}"

    bucket = _bucket_for_brand(brand)

    # --- generate presigned PUT URL (boto3 signs locally, no network call) ---
    client = _s3_client()
    try:
        presigned_url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=300,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"R2 presign failed: {exc}",
        ) from exc

    # --- upload via httpx (bypasses boto3's SSL layer entirely) ---
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.put(
                presigned_url,
                content=data,
                headers={"Content-Type": content_type},
            )
        if resp.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"R2 upload failed: HTTP {resp.status_code} — {resp.text[:200]}",
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"R2 upload request error: {exc}",
        ) from exc

    return _public_url(bucket, key)


async def delete_image(key: str, brand: str) -> None:
    """Delete an object from a brand's R2 bucket by its key (path after the domain)."""
    bucket = _bucket_for_brand(brand)
    client = _s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"R2 delete failed: {exc}",
        ) from exc
