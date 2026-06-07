from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

from . import database
from .checksum import read_checksums, sha256_file
from .config import Config
from .crypto import decrypt_file
from .exceptions import GitError, NxbakError
from .git import commit_in_branch, latest_commit, show_binary_file, show_file
from .manifest import read_manifest


def load_snapshot(repo_root: Path, config: Config, *, snapshot_type: str, commit: str | None = None) -> tuple[str, dict, Path, tempfile.TemporaryDirectory]:
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
    backup_name = manifest["files"][0]["name"]
    backup_path = tmp / backup_name
    show_binary_file(repo_root, selected_commit, backup_name, backup_path)

    expected = manifest["files"][0]["sha256"]
    actual = sha256_file(backup_path)
    if expected != actual or checksums.get(backup_name) != actual:
        tmp_ctx.cleanup()
        raise NxbakError("Snapshot checksum verification failed.")

    return selected_commit, manifest, backup_path, tmp_ctx


def prepare_restore_file(config: Config, manifest: dict, backup_path: Path) -> Path:
    if manifest.get("encrypted"):
        decrypted = backup_path.with_suffix("")
        decrypt_file(backup_path, decrypted, config.encryption_key or "")
        return decrypted
    return backup_path


def restore_snapshot(repo_root: Path, config: Config, *, snapshot_type: str, commit: str | None, dry_run: bool) -> dict[str, str]:
    selected_commit, manifest, backup_path, tmp_ctx = load_snapshot(repo_root, config, snapshot_type=snapshot_type, commit=commit)
    try:
        restore_file = prepare_restore_file(config, manifest, backup_path)
        database.check_connection(config.database_url)
        if not dry_run:
            database.restore_database(config.database_url, restore_file)
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
    selected_commit, manifest, backup_path, tmp_ctx = load_snapshot(repo_root, config, snapshot_type=snapshot_type, commit=commit)
    try:
        restore_file = prepare_restore_file(config, manifest, backup_path)
        target_dir = output_dir / selected_commit[:7]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_dump = target_dir / "database.dump.gz"
        shutil.copy2(restore_file, target_dump)
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
