from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import database
from .checksum import read_checksums, sha256_file
from .config import Config
from .crypto import decrypt_file
from .exceptions import GitError
from .git import commit_in_branch, latest_commit, show_binary_file, show_file
from .manifest import read_manifest


def load_snapshot(repo_root: Path, config: Config, *, snapshot_type: str, commit: str | None = None, progress=None) -> tuple[str, dict, list[Path], tempfile.TemporaryDirectory]:
    """Load snapshot files from Git. Returns (commit, manifest, list_of_backup_paths, tmp_ctx).
    
    Checksum verification is done as a warning only — it never blocks restore.
    """
    log = progress or (lambda _message: None)
    branch = config.branch_for_type(snapshot_type)
    selected_commit = commit or latest_commit(repo_root, config.remote, branch)
    if not commit_in_branch(repo_root, config.remote, branch, selected_commit):
        raise GitError(f"Commit '{selected_commit}' is not part of branch '{branch}'.")

    tmp_ctx = tempfile.TemporaryDirectory(prefix="nxbak-restore-")
    tmp = Path(tmp_ctx.name)
    manifest_path = tmp / "manifest.json"
    checksums_path = tmp / "checksums.sha256"
    show_file(repo_root, selected_commit, "manifest.json", manifest_path)
    show_file(repo_root, selected_commit, "checksums.sha256", checksums_path)
    manifest = read_manifest(manifest_path)
    checksums = read_checksums(checksums_path)

    # Load all backup files from manifest
    backup_paths: list[Path] = []
    for file_entry in manifest["files"]:
        backup_name = file_entry["name"]
        backup_path = tmp / backup_name
        show_binary_file(repo_root, selected_commit, backup_name, backup_path)
        backup_paths.append(backup_path)

        # Checksum verification: warn only, never block
        expected = file_entry["sha256"]
        actual = sha256_file(backup_path)
        if expected != actual or checksums.get(backup_name) != actual:
            log(f"[WARNING] Checksum mismatch for {backup_name} — continuing anyway")

    return selected_commit, manifest, backup_paths, tmp_ctx


def prepare_restore_files(config: Config, manifest: dict, backup_paths: list[Path]) -> list[Path]:
    """Decrypt backup files if encrypted. Returns list of restore-ready paths."""
    if manifest.get("encrypted"):
        decrypted_paths: list[Path] = []
        for backup_path in backup_paths:
            decrypted = backup_path.with_suffix("")
            decrypt_file(backup_path, decrypted, config.encryption_key or "")
            decrypted_paths.append(decrypted)
        return decrypted_paths
    return backup_paths


def restore_snapshot(
    repo_root: Path,
    config: Config,
    *,
    snapshot_type: str,
    commit: str | None,
    dry_run: bool,
    progress=None,
) -> dict[str, str]:
    log = progress or (lambda _message: None)
    log("Loading snapshot from Git")
    selected_commit, manifest, backup_paths, tmp_ctx = load_snapshot(
        repo_root, config, snapshot_type=snapshot_type, commit=commit, progress=progress
    )
    try:
        log("Verifying checksum and decrypting snapshot")
        restore_files = prepare_restore_files(config, manifest, backup_paths)
        log("Checking database connection")
        database.check_connection(config.database_url)
        if not dry_run:
            for restore_file in restore_files:
                log(f"Restoring {restore_file.name} with pg_restore")
                database.restore_dump(config.database_url, restore_file)
        return {
            "type": manifest["backup_type"],
            "commit": selected_commit[:7],
            "created": manifest["created_at"],
            "encrypted": "yes" if manifest.get("encrypted") else "no",
            "mode": "dry-run" if dry_run else "restored",
        }
    finally:
        tmp_ctx.cleanup()


def decrypt_snapshot(repo_root: Path, config: Config, *, snapshot_type: str, commit: str | None, output_dir: Path) -> dict[str, str]:
    selected_commit, manifest, backup_paths, tmp_ctx = load_snapshot(
        repo_root, config, snapshot_type=snapshot_type, commit=commit
    )
    try:
        restore_files = prepare_restore_files(config, manifest, backup_paths)
        target_dir = output_dir / selected_commit[:7]
        target_dir.mkdir(parents=True, exist_ok=True)
        for restore_file in restore_files:
            shutil.copy2(restore_file, target_dir / restore_file.name)
        shutil.copy2(Path(tmp_ctx.name) / "manifest.json", target_dir / "manifest.json")
        shutil.copy2(Path(tmp_ctx.name) / "checksums.sha256", target_dir / "checksums.sha256")
        return {
            "type": manifest["backup_type"],
            "commit": selected_commit[:7],
            "created": manifest["created_at"],
            "encrypted": "yes" if manifest.get("encrypted") else "no",
            "output": str(target_dir),
        }
    finally:
        tmp_ctx.cleanup()
