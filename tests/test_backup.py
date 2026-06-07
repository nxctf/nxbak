from pathlib import Path

from nxbak.backup import create_backup
from nxbak.config import BackupConfig, Branches, Config, RestoreConfig, SourceConfig


def test_backup_uses_daily_branch(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_dump_schema(_url, target, schemas):
        seen["schemas"] = schemas
        target.write_bytes(b"dump")

    def fake_dump_auth(_url, target, tables):
        seen["tables"] = tables
        target.write_bytes(b"auth")

    class fake_worktree:
        def __enter__(self):
            return tmp_path

        def __exit__(self, *args):
            return False

    monkeypatch.setenv("DB_URL", "postgresql://secret")
    monkeypatch.setenv("KEY", "secret-key")
    monkeypatch.setattr("nxbak.backup.database.dump_schema", fake_dump_schema)
    monkeypatch.setattr("nxbak.backup.database.dump_auth_tables", fake_dump_auth)
    monkeypatch.setattr("nxbak.backup.snapshot_worktree", lambda root, remote, branch: fake_worktree())

    def fake_replace(_worktree, files, _message, _remote, branch):
        seen["branch"] = branch
        seen["files"] = [file.name for file in files]
        return "abc1234"

    monkeypatch.setattr("nxbak.backup.replace_snapshot_files", fake_replace)
    config = Config(
        version=1,
        remote="origin",
        branches=Branches(),
        source=SourceConfig(database_url_env="DB_URL"),
        backup=BackupConfig(encryption=True, encryption_key_env="KEY"),
        restore=RestoreConfig(),
    )
    messages = []
    result = create_backup(tmp_path, config, snapshot_type="daily", progress=messages.append)
    assert result["commit"] == "abc1234"
    assert seen["branch"] == "snapshots/daily"
    assert seen["schemas"] == ("public",)
    assert "database.dump.gz.enc" in seen["files"]
    assert "Dumping schema objects with pg_dump: public" in messages
    assert "Committing and pushing snapshot to snapshots/daily" in messages
