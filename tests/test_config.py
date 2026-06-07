from pathlib import Path

from nxbak.config import load_config


def test_load_config(tmp_path: Path):
    (tmp_path / ".nxbak.yml").write_text(
        """
version: 1
remote: origin
branches:
  manual: snapshots/manual
  daily: snapshots/daily
  monthly: snapshots/monthly
source:
  type: supabase
  database_url_env: DB_URL
backup:
  compression: gzip
  encryption: false
  schemas:
    - public
    - private
  include_auth_data: true
restore:
  schemas:
    - public
  include_auth_data: true
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.source.database_url_env == "DB_URL"
    assert config.branch_for(False) == "snapshots/manual"
    assert config.branch_for(True) == "snapshots/daily"
    assert config.branch_for(manual=True) == "snapshots/manual"
    assert config.branch_for(monthly=True) == "snapshots/monthly"
    assert config.snapshot_types() == ["manual", "daily", "monthly"]
    assert config.backup.schemas == ("public", "private")
    assert config.restore.schemas == ("public",)
    assert config.backup.include_auth_data is True
    assert config.restore.include_auth_data is True
    assert config.backup.auth_tables == ("auth.users", "auth.identities", "auth.audit_log_entries")
    assert config.restore.auth_tables == ("auth.users", "auth.identities", "auth.audit_log_entries")
