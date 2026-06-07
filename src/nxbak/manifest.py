from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .checksum import sha256_file


@dataclass(frozen=True)
class ManifestFile:
    name: str
    sha256: str
    size: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_manifest(*, backup_type: str, encrypted: bool, backup_files: list[Path], created_at: str | None = None) -> dict:
    return {
        "version": 1,
        "tool": "nxbak",
        "backup_type": backup_type,
        "created_at": created_at or utc_now_iso(),
        "source_type": "supabase",
        "compression": "gzip",
        "encrypted": encrypted,
        "files": [
            {
                "name": backup_file.name,
                "sha256": sha256_file(backup_file),
                "size": backup_file.stat().st_size,
            }
            for backup_file in backup_files
        ],
    }


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
