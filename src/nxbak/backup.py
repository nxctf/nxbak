from __future__ import annotations

import tempfile
from pathlib import Path

from . import database
from .checksum import write_checksums
from .config import Config
from .crypto import encrypt_file
from .git import replace_snapshot_files, snapshot_worktree
from .manifest import create_manifest, utc_now_iso, write_manifest


def create_backup(repo_root: Path, config: Config, *, snapshot_type: str, progress=None) -> dict[str, str]:
    backup_type = snapshot_type
    branch = config.branch_for_type(snapshot_type)
    created_at = utc_now_iso()
    log = progress or (lambda _message: None)

    with tempfile.TemporaryDirectory(prefix="nxbak-backup-") as tmp_name:
        tmp = Path(tmp_name)
        backup_files: list[Path] = []

        # Pass 1: dump full public schema (tables, data, triggers, functions, sequences, etc.)
        schema_plain = tmp / "database.dump.gz"
        log(f"Dumping schema objects with pg_dump: {', '.join(config.backup.schemas)}")
        database.dump_schema(config.database_url, schema_plain, config.backup.schemas)

        # Pass 2: dump auth tables separately (they live outside the selected schemas)
        if config.backup.auth_tables:
            auth_plain = tmp / "auth.dump.gz"
            log(f"Dumping auth tables with pg_dump: {', '.join(config.backup.auth_tables)}")
            database.dump_auth_tables(config.database_url, auth_plain, config.backup.auth_tables)

        encrypted = bool(config.backup.encryption)
        if encrypted:
            log("Encrypting compressed dumps")
            schema_enc = tmp / "database.dump.gz.enc"
            encrypt_file(schema_plain, schema_enc, config.encryption_key or "")
            schema_plain.unlink(missing_ok=True)
            backup_files.append(schema_enc)

            if config.backup.auth_tables:
                auth_enc = tmp / "auth.dump.gz.enc"
                encrypt_file(auth_plain, auth_enc, config.encryption_key or "")
                auth_plain.unlink(missing_ok=True)
                backup_files.append(auth_enc)
        else:
            backup_files.append(schema_plain)
            if config.backup.auth_tables:
                backup_files.append(auth_plain)

        log("Writing manifest and checksum")
        manifest = create_manifest(
            backup_type=backup_type,
            encrypted=encrypted,
            backup_files=backup_files,
            created_at=created_at,
        )
        manifest_path = tmp / "manifest.json"
        checksums_path = tmp / "checksums.sha256"
        write_manifest(manifest_path, manifest)
        write_checksums(checksums_path, backup_files)

        message = f"NXBAK {backup_type} snapshot: {created_at}"
        log(f"Preparing snapshot branch {branch}")
        with snapshot_worktree(repo_root, config.remote, branch) as worktree:
            log(f"Committing and pushing snapshot to {branch}")
            commit = replace_snapshot_files(
                worktree,
                [manifest_path, *backup_files, checksums_path],
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
