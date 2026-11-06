import os
from pathlib import Path
from uuid import uuid4

import boto3


MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


def save_photo(filename: str, content_type: str, content: bytes) -> str:
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise ValueError("Photos must be JPEG, PNG, or WebP images.")
    if not content or len(content) > MAX_PHOTO_BYTES:
        raise ValueError("Each photo must be between 1 byte and 10 MB.")
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
    key = f"evidence/{uuid4().hex}{suffix}"
    bucket = os.getenv("EVIDENCE_BUCKET_NAME")
    if bucket:
        boto3.client("s3", region_name=os.getenv("AWS_REGION", "eu-central-1")).put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return key
    upload_root = Path(os.getenv("LOCAL_UPLOAD_DIR", "/app/uploads"))
    upload_root.mkdir(parents=True, exist_ok=True)
    (upload_root / f"{Path(key).name}").write_bytes(content)
    return key
