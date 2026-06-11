from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from .config import Settings


@dataclass(slots=True)
class MinioMarkdownObject:
    bucket: str
    object_name: str
    source_path: str
    source_name: str
    parent_name: str
    etag: str
    last_modified: str
    text: str


def build_minio_source_path(bucket: str, object_name: str) -> str:
    normalized_name = object_name.strip("/")
    return f"minio://{bucket}/{normalized_name}"


class MinioMarkdownBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_markdown_objects(self, bucket: str, prefix: str = "") -> list[str]:
        client = self._client()
        normalized_prefix = prefix.strip("/")
        objects: list[str] = []
        for obj in client.list_objects(bucket, prefix=normalized_prefix, recursive=True):
            object_name = str(getattr(obj, "object_name", "") or "")
            if not object_name or object_name.endswith("/"):
                continue
            if object_name.lower().endswith(".md"):
                objects.append(object_name)
        return sorted(objects)

    def get_markdown_object(self, bucket: str, object_name: str) -> MinioMarkdownObject:
        client = self._client()
        normalized_name = object_name.strip("/")
        stat = client.stat_object(bucket, normalized_name)
        response = client.get_object(bucket, normalized_name)
        try:
            raw_bytes = response.read()
        finally:
            response.close()
            response.release_conn()

        source_path = build_minio_source_path(bucket, normalized_name)
        object_path = PurePosixPath(normalized_name)
        last_modified = getattr(stat, "last_modified", "")
        etag = str(getattr(stat, "etag", "") or "").strip('"')

        return MinioMarkdownObject(
            bucket=bucket,
            object_name=normalized_name,
            source_path=source_path,
            source_name=object_path.name,
            parent_name=object_path.parent.name if object_path.parent.name else "",
            etag=etag,
            last_modified=_to_isoformat(last_modified),
            text=_decode_text(raw_bytes),
        )

    def _client(self):
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError(
                "MinIO Python client is not installed in the current environment. "
                "Run `pip install minio` or `pip install -e .` in the stock environment."
            ) from exc

        return Minio(
            self.settings.minio_endpoint,
            access_key=self.settings.minio_access_key,
            secret_key=self.settings.minio_secret_key,
            secure=self.settings.minio_secure,
        )


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _to_isoformat(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")
