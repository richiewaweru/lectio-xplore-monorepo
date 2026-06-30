from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from core.config import settings
from core.storage.gcs_image_store import GCSImageStore as CoreGCSImageStore


logger = logging.getLogger(__name__)


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
        self.bucket_name = bucket_name
        self._core_store = CoreGCSImageStore(bucket_name=bucket_name)
        self.base_url = self._core_store._base_url.rstrip("/")
        self.credential_source = self._core_store.credential_source
        self.credentials_resolved = self._core_store.credentials_resolved
        self.client = self._core_store.client

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
        content_type = f"image/{format}"

        logger.info(
            "v3 visual gcs upload start",
            extra={
                "node_name": "visual_executor",
                "generation_id": generation_id,
                "bucket_name": self.bucket_name,
                "blob_path": blob_path,
                "credential_source": self.credential_source,
                "credentials_resolved": self.credentials_resolved,
                "auth_client": type(self.client).__name__ if self.client is not None else None,
                "content_type": content_type,
                "byte_count": len(image_bytes),
            },
        )
        try:
            final_url = await self._core_store.upload_with_key(
                key=blob_path,
                image_bytes=image_bytes,
                content_type=content_type,
            )
            if not final_url:
                raise RuntimeError("GCS upload returned no URL")
            logger.info(
                "v3 visual gcs upload complete",
                extra={
                    "node_name": "visual_executor",
                    "generation_id": generation_id,
                    "bucket_name": self.bucket_name,
                    "blob_path": blob_path,
                    "credential_source": self.credential_source,
                    "credentials_resolved": self.credentials_resolved,
                    "auth_client": type(self.client).__name__ if self.client is not None else None,
                    "final_url": final_url,
                },
            )
            return final_url
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "v3 visual gcs upload failed",
                extra={
                    "node_name": "visual_executor",
                    "generation_id": generation_id,
                    "bucket_name": self.bucket_name,
                    "blob_path": blob_path,
                    "credential_source": self.credential_source,
                    "credentials_resolved": self.credentials_resolved,
                    "auth_client": type(self.client).__name__ if self.client is not None else None,
                },
                exc_info=exc,
            )
            raise

    async def probe_write_access(self) -> tuple[bool, str]:
        return await asyncio.to_thread(self._core_probe)

    def _core_probe(self) -> tuple[bool, str]:
        bucket = self._core_store._bucket
        if bucket is None:
            return False, "GCS bucket is not configured"
        if not bucket.exists():
            return False, f"GCS bucket '{self.bucket_name}' is not accessible"

        permissions = bucket.test_iam_permissions(["storage.objects.create"])
        if "storage.objects.create" not in permissions:
            return (
                False,
                f"GCS bucket '{self.bucket_name}' is missing storage.objects.create permission",
            )

        return (
            True,
            f"GCS bucket '{self.bucket_name}' writable via {self.credential_source}",
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

