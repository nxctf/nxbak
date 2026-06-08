from pathlib import Path

from nxbak.config import BackupConfig, Branches, Config, RestoreConfig, SourceConfig
from nxbak.manifest import create_manifest, write_manifest
from nxbak.restore import decrypt_snapshot, restore_snapshot


def test_restore_dry_run(monkeypatch, tmp_path: Path):
    backup = tmp_path / "database.dump.gz"
    backup.write_bytes(b"dump")
    manifest = create_manifest(backup_type="manual", encrypted=False, backup_files=[backup], created_at="2026-06-07T02:00:00Z")
    write_manifest(tmp_path / "manifest.json", manifest)
    (tmp_path / "checksums.sha256").write_text(f"{manifest['files'][0]['sha256']}  database.dump.gz\n", encoding="utf-8")

    monkeypatch.setenv("DB_URL", "postgresql://secret")
    monkeypatch.setattr("nxbak.restore.latest_commit", lambda *_: "abc1234")
    monkeypatch.setattr("nxbak.restore.commit_in_branch", lambda *_: True)
    monkeypatch.setattr("nxbak.restore.show_file", lambda _root, _commit, path, target: target.write_text((tmp_path / path).read_text(encoding="utf-8"), encoding="utf-8"))
    monkeypatch.setattr("nxbak.restore.show_binary_file", lambda _root, _commit, path, target: target.write_bytes((tmp_path / path).read_bytes()))
    monkeypatch.setattr("nxbak.restore.database.check_connection", lambda _url: None)
    called = {"restore": False}
    monkeypatch.setattr("nxbak.restore.database.restore_dump", lambda *_: called.update(restore=True))

    config = Config(1, "origin", Branches(), SourceConfig(database_url_env="DB_URL"), BackupConfig(encryption=False), RestoreConfig())
    messages = []
    result = restore_snapshot(tmp_path, config, snapshot_type="manual", commit=None, dry_run=True, progress=messages.append)
    assert result["mode"] == "dry-run"
    assert called["restore"] is False
    assert "Loading snapshot from Git" in messages
    assert "Checking database connection" in messages


def test_decrypt_snapshot_writes_output(monkeypatch, tmp_path: Path):
    backup = tmp_path / "database.dump.gz"
    backup.write_bytes(b"dump")
    manifest = create_manifest(backup_type="manual", encrypted=False, backup_files=[backup], created_at="2026-06-07T02:00:00Z")
    write_manifest(tmp_path / "manifest.json", manifest)
    (tmp_path / "checksums.sha256").write_text(f"{manifest['files'][0]['sha256']}  database.dump.gz\n", encoding="utf-8")

    monkeypatch.setenv("DB_URL", "postgresql://secret")
    monkeypatch.setattr("nxbak.restore.commit_in_branch", lambda *_: True)
    monkeypatch.setattr("nxbak.restore.show_file", lambda _root, _commit, path, target: target.write_text((tmp_path / path).read_text(encoding="utf-8"), encoding="utf-8"))
    monkeypatch.setattr("nxbak.restore.show_binary_file", lambda _root, _commit, path, target: target.write_bytes((tmp_path / path).read_bytes()))

    config = Config(1, "origin", Branches(), SourceConfig(database_url_env="DB_URL"), BackupConfig(encryption=False), RestoreConfig())
    result = decrypt_snapshot(tmp_path, config, snapshot_type="manual", commit="abc123456", output_dir=tmp_path / "out")
    assert result["output"].endswith("abc1234")
    assert (tmp_path / "out" / "abc1234" / "database.dump.gz").read_bytes() == b"dump"
    assert (tmp_path / "out" / "abc1234" / "manifest.json").exists()
