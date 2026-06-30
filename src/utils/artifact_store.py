"""GCS artifact helpers for run_id directories."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GcsPrefix:
    bucket: str
    prefix: str

    @classmethod
    def parse(cls, uri: str) -> "GcsPrefix":
        if not uri.startswith("gs://"):
            raise ValueError(f"not a GCS URI: {uri}")
        path = uri.removeprefix("gs://").strip("/")
        bucket, _, prefix = path.partition("/")
        if not bucket:
            raise ValueError(f"GCS URI must include bucket: {uri}")
        return cls(bucket=bucket, prefix=prefix.strip("/"))

    def uri(self, *parts: str) -> str:
        joined = "/".join(p.strip("/") for p in parts if p)
        base = f"gs://{self.bucket}" + (f"/{self.prefix}" if self.prefix else "")
        return f"{base}/{joined}" if joined else base


def upload_directory(local_dir: Path, destination: GcsPrefix) -> list[str]:
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(destination.bucket)
    uploaded: list[str] = []
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        blob_name = f"{destination.prefix}/{rel}" if destination.prefix else rel
        bucket.blob(blob_name).upload_from_filename(str(path))
        uploaded.append(f"gs://{destination.bucket}/{blob_name}")
    return uploaded


def download_directory(source: GcsPrefix, local_dir: Path) -> list[Path]:
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(source.bucket)
    local_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for blob in client.list_blobs(source.bucket, prefix=source.prefix):
        if blob.name.endswith("/"):
            continue
        rel = Path(blob.name).relative_to(source.prefix) if source.prefix else Path(blob.name)
        path = local_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        bucket.blob(blob.name).download_to_filename(str(path))
        downloaded.append(path)
    return downloaded


def latest_run_id(bucket_name: str, competition: str) -> str:
    from google.cloud import storage

    prefix = f"runs/{competition}/"
    client = storage.Client()
    run_ids = {
        blob.name.removeprefix(prefix).split("/", 1)[0]
        for blob in client.list_blobs(bucket_name, prefix=prefix)
        if blob.name.removeprefix(prefix).split("/", 1)[0]
    }
    if not run_ids:
        raise SystemExit(f"[collect] no runs found under gs://{bucket_name}/{prefix}")
    return sorted(run_ids)[-1]
