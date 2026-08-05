from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class OssConfig:
    endpoint: str
    bucket: str
    access_key_id: str
    access_key_secret: str


def upload_file(config: OssConfig, local_path: str | Path, object_key: str) -> str:
    import oss2

    auth = oss2.Auth(config.access_key_id, config.access_key_secret)
    bucket = oss2.Bucket(auth, config.endpoint, config.bucket)
    bucket.put_object_from_file(object_key, str(local_path))
    return f"oss://{config.bucket}/{object_key}"


def build_media_pending_row(*, source_table: str, source_pk: str | int, media_type: str, origin_url: str, target_key: str = "") -> dict:
    return {
        "source_table": source_table,
        "source_pk": str(source_pk),
        "media_type": media_type,
        "origin_url": origin_url,
        "target_key": target_key,
        "status": "PENDING",
    }
