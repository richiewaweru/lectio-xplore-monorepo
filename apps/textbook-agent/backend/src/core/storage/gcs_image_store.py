from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import timedelta

from google.cloud import storage
from google.oauth2 import service_account

logger = logging.getLogger(__name__)
_PRODUCTION_LIKE_ENVS = {"production", "staging"}


class GCSImageStore:
    """
    Upload pipeline images to GCS and return a URL.

    Key format : images/{generation_id}/{section_id}.png
    URL         : signed URL (1-hour TTL) unless GCS_IMAGE_BASE_URL is set
    No-op mode  : when GCS_BUCKET_NAME is empty, enabled=False and all
                  operations return None — lets local dev run without credentials.
    """

    def __init__(self, bucket_name: str | None = None) -> None:
        resolved_bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME", "")
        self.bucket_name = resolved_bucket_name
        self.credential_source = "application_default"
        self.credentials_resolved = False
        self.client = None
        if not resolved_bucket_name:
            self._bucket = None
            self._base_url = ""
            return

        creds_json = os.getenv("GCS_SERVICE_ACCOUNT_JSON", "")
        if creds_json:
            info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            client = storage.Client(
                credentials=credentials,
                project=info["project_id"],
            )
            self.credential_source = "service_account_json"
            self.credentials_resolved = True
        else:
            # Local fallback: gcloud auth application-default login
            client = storage.Client()

        self.client = client
        self._bucket = client.bucket(resolved_bucket_name)
        self._base_url = os.getenv("GCS_IMAGE_BASE_URL", "")
        app_env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()
        if app_env in _PRODUCTION_LIKE_ENVS and not self._base_url:
            logger.warning("GCS image store falling back to expiring signed URLs in production")

    @property
    def enabled(self) -> bool:
        return self._bucket is not None

    async def upload(
        self,
        *,
        generation_id: str,
        section_id: str,
        image_bytes: bytes,
        content_type: str = "image/png",
    ) -> str | None:
        """
        Upload bytes and return a publicly-accessible URL.
        Returns None if GCS is not configured.
        """
        if not self.enabled:
            return None

        key = f"images/{generation_id}/{section_id}.png"
        return await self.upload_with_key(
            key=key,
            image_bytes=image_bytes,
            content_type=content_type,
        )

    async def upload_with_key(
        self,
        *,
        key: str,
        image_bytes: bytes,
        content_type: str = "image/png",
    ) -> str | None:
        """Upload bytes to a specific object key and return an accessible URL."""
        if not self.enabled:
            return None

        blob = self._bucket.blob(key)
        await asyncio.to_thread(blob.upload_from_string, image_bytes, content_type)

        if self._base_url:
            return f"{self._base_url.rstrip('/')}/{key}"

        return blob.generate_signed_url(
            expiration=timedelta(hours=1),
            method="GET",
            version="v4",
        )

    async def exists(self, *, key: str) -> bool:
        if not self.enabled:
            return False
        blob = self._bucket.blob(key)
        return await asyncio.to_thread(blob.exists)

    async def download_with_key(self, *, key: str) -> bytes | None:
        """Download object bytes by internal key; never resolves arbitrary URLs."""
        if not self.enabled:
            return None
        clean = key.strip().replace("\\", "/").lstrip("/")
        if not clean or "://" in clean or any(part in {".", ".."} for part in clean.split("/")):
            raise ValueError("unsafe GCS image key")
        blob = self._bucket.blob(clean)
        if not await asyncio.to_thread(blob.exists):
            return None
        return await asyncio.to_thread(blob.download_as_bytes)

    async def copy(self, *, source_key: str, destination_key: str) -> str | None:
        if not self.enabled:
            return None
        source_blob = self._bucket.blob(source_key)
        await asyncio.to_thread(self._bucket.copy_blob, source_blob, self._bucket, destination_key)
        if self._base_url:
            return f"{self._base_url.rstrip('/')}/{destination_key}"
        copied_blob = self._bucket.blob(destination_key)
        return copied_blob.generate_signed_url(
            expiration=timedelta(hours=1),
            method="GET",
            version="v4",
        )
