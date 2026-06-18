from __future__ import annotations

from pathlib import Path

from core.config import settings
from pipeline.media.storage.image_store import GCSImageStore, ImageStore, LocalImageStore


def get_image_store() -> ImageStore:
    if settings.app_env == "production":
        return GCSImageStore(bucket_name=settings.gcs_bucket_name)
    return LocalImageStore(base_path=Path("data/images"), base_url=settings.image_base_url)


__all__ = ["GCSImageStore", "ImageStore", "LocalImageStore", "get_image_store", "settings"]
