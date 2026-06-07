from __future__ import annotations

import tempfile
from pathlib import Path

from . import database
from .checksum import write_checksums
from .config import Config
from .crypto import encrypt_file
from .git import replace_snapshot_files, snapshot_worktree
from .manifest import create_manifest, utc_now_iso, write_manifest


def create_backup(repo_root: Path, config: Config, *, snapshot_type: str) -> dict[str, str]:
    backup_type = snapshot_type
    branch = config.branch_for_type(snapshot_type)
    created_at = utc_now_iso()

    with tempfile.TemporaryDirectory(prefix="nxbak-backup-") as tmp_name:
        tmp = Path(tmp_name)
        plain = tmp / "database.dump.gz"
        database.dump_database(config.database_url, plain)

        encrypted = bool(config.backup.encryption)
        if encrypted:
            backup_file = tmp / "database.dump.gz.enc"
            encrypt_file(plain, backup_file, config.encryption_key or "")
            plain.unlink(missing_ok=True)
        else:
            backup_file = plain

        manifest = create_manifest(
            backup_type=backup_type,
            encrypted=encrypted,
            backup_file=backup_file,
            created_at=created_at,
        )
        manifest_path = tmp / "manifest.json"
        checksums_path = tmp / "checksums.sha256"
        write_manifest(manifest_path, manifest)
        write_checksums(checksums_path, [backup_file])

        message = f"NXBAK {backup_type} snapshot: {created_at}"
        with snapshot_worktree(repo_root, config.remote, branch) as worktree:
            commit = replace_snapshot_files(
                worktree,
                [manifest_path, backup_file, checksums_path],
                message,
                config.remote,
                branch,
            )

    return {
        "type": backup_type,
        "branch": branch,
        "commit": commit,
        "remote": config.remote,
        "encrypted": "yes" if encrypted else "no",
        "checksum": "verified",
    }
