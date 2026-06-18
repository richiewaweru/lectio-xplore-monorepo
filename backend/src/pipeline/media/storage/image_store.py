from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from core.config import settings


class ImageStore(ABC):
    @abstractmethod
    async def store_image(
        self,
        image_bytes: bytes,
        *,
        generation_id: str,
        section_id: str,
        filename: str,
        format: str = "png",
    ) -> str:
        ...

    @abstractmethod
    async def probe_write_access(self) -> tuple[bool, str]:
        ...

    @abstractmethod
    def describe_target(self) -> str:
        ...


class LocalImageStore(ImageStore):
    def __init__(self, base_path: Path, base_url: str):
        self.base_path = base_path
        self.base_url = base_url.rstrip("/")
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store_image(
        self,
        image_bytes: bytes,
        *,
        generation_id: str,
        section_id: str,
        filename: str,
        format: str = "png",
    ) -> str:
        _ = format
        dir_path = self.base_path / generation_id / section_id
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename
        file_path.write_bytes(image_bytes)
        return f"{self.base_url}/{generation_id}/{section_id}/{filename}"

    async def probe_write_access(self) -> tuple[bool, str]:
        probe_dir = self.base_path / "_health"
        probe_file = probe_dir / f".probe-{uuid4().hex}"

        try:
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe_file.write_bytes(b"ok")
            probe_file.unlink(missing_ok=True)
        except Exception as exc:
            return False, f"local write failed at {self.base_path}: {type(exc).__name__}: {exc}"

        return True, f"local path writable at {self.base_path}"

    def describe_target(self) -> str:
        return f"local:{self.base_path}"


class GCSImageStore(ImageStore):
    def __init__(self, bucket_name: str):
        from google.cloud import storage
        from google.oauth2 import service_account

        self.bucket_name = bucket_name
        self.base_url = os.getenv("GCS_IMAGE_BASE_URL", "").rstrip("/")
        creds_json = os.getenv("GCS_SERVICE_ACCOUNT_JSON", "").strip()
        self.credential_source = "application_default"

        if creds_json:
            info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            self.client = storage.Client(
                credentials=credentials,
                project=info.get("project_id"),
            )
            self.credential_source = "service_account_json"
        else:
            self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    async def store_image(
        self,
        image_bytes: bytes,
        *,
        generation_id: str,
        section_id: str,
        filename: str,
        format: str = "png",
    ) -> str:
        blob_path = f"{generation_id}/{section_id}/{filename}"
        blob = self.bucket.blob(blob_path)

        def _upload() -> str:
            blob.upload_from_string(image_bytes, content_type=f"image/{format}")
            if self.base_url:
                return f"{self.base_url}/{blob_path}"
            blob.make_public()
            return blob.public_url

        return await asyncio.to_thread(_upload)

    async def probe_write_access(self) -> tuple[bool, str]:
        def _probe() -> tuple[bool, str]:
            if not self.bucket.exists():
                return False, f"GCS bucket '{self.bucket_name}' is not accessible"

            permissions = self.bucket.test_iam_permissions(["storage.objects.create"])
            if "storage.objects.create" not in permissions:
                return (
                    False,
                    f"GCS bucket '{self.bucket_name}' is missing storage.objects.create permission",
                )

            return (
                True,
                f"GCS bucket '{self.bucket_name}' writable via {self.credential_source}",
            )

        try:
            return await asyncio.to_thread(_probe)
        except Exception as exc:
            return (
                False,
                f"GCS write probe failed for '{self.bucket_name}': {type(exc).__name__}: {exc}",
            )

    def describe_target(self) -> str:
        if self.base_url:
            return f"gcs:{self.bucket_name} base_url={self.base_url}"
        return f"gcs:{self.bucket_name} auth={self.credential_source}"


def get_image_store() -> ImageStore:
    env = settings.app_env
    if env == "production":
        return GCSImageStore(bucket_name=settings.gcs_bucket_name)
    return LocalImageStore(base_path=Path("data/images"), base_url=settings.image_base_url)
