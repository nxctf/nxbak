from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from .exceptions import ConfigError


@dataclass(frozen=True)
class Branches:
    manual: str = "snapshots/manual"
    daily: str = "snapshots/daily"
    monthly: str = "snapshots/monthly"


@dataclass(frozen=True)
class SourceConfig:
    type: str = "supabase"
    database_url_env: str = "NXBAK_SUPABASE_DB_URL"


@dataclass(frozen=True)
class BackupConfig:
    compression: str = "gzip"
    encryption: bool = True
    encryption_key_env: str = "NXBAK_ENCRYPTION_KEY"


@dataclass(frozen=True)
class RestoreConfig:
    verify_checksum: bool = True
    require_confirmation: bool = True


@dataclass(frozen=True)
class Config:
    version: int
    remote: str
    branches: Branches
    source: SourceConfig
    backup: BackupConfig
    restore: RestoreConfig

    def branch_for(self, daily: bool = False, monthly: bool = False) -> str:
        return self.branch_for_type(self.type_for(daily=daily, monthly=monthly))

    def branch_for_type(self, snapshot_type: str) -> str:
        if snapshot_type == "manual":
            return self.branches.manual
        if snapshot_type == "daily":
            return self.branches.daily
        if snapshot_type == "monthly":
            return self.branches.monthly
        raise ConfigError(f"Unknown snapshot type '{snapshot_type}'.")

    def type_for(self, daily: bool = False, monthly: bool = False) -> str:
        if daily and monthly:
            raise ConfigError("Choose only one snapshot type: --daily or --monthly.")
        if monthly:
            return "monthly"
        if daily:
            return "daily"
        return "manual"

    def snapshot_types(self) -> list[str]:
        return ["manual", "daily", "monthly"]

    @property
    def database_url(self) -> str:
        value = os.getenv(self.source.database_url_env)
        if not value:
            raise ConfigError(f"Environment variable '{self.source.database_url_env}' is required.")
        return value

    @property
    def encryption_key(self) -> str | None:
        if not self.backup.encryption:
            return None
        value = os.getenv(self.backup.encryption_key_env)
        if not value:
            raise ConfigError(f"Environment variable '{self.backup.encryption_key_env}' is required.")
        return value


def load_config(repo_root: Path) -> Config:
    path = repo_root / ".nxbak.yml"
    if not path.exists():
        raise ConfigError("NXBAK config '.nxbak.yml' was not found. Copy .nxbak.example.yml first.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("version") != 1:
        raise ConfigError("Unsupported or missing config version. Expected version: 1.")
    source = data.get("source") or {}
    if source.get("type", "supabase") != "supabase":
        raise ConfigError("Only source.type='supabase' is supported.")
    backup = data.get("backup") or {}
    if backup.get("compression", "gzip") != "gzip":
        raise ConfigError("Only backup.compression='gzip' is supported.")
    branches = data.get("branches") or {}
    restore = data.get("restore") or {}
    return Config(
        version=1,
        remote=data.get("remote", "origin"),
        branches=Branches(
            manual=branches.get("manual", "snapshots/manual"),
            daily=branches.get("daily", "snapshots/daily"),
            monthly=branches.get("monthly", "snapshots/monthly"),
        ),
        source=SourceConfig(database_url_env=source.get("database_url_env", "NXBAK_SUPABASE_DB_URL")),
        backup=BackupConfig(
            compression="gzip",
            encryption=bool(backup.get("encryption", True)),
            encryption_key_env=backup.get("encryption_key_env", "NXBAK_ENCRYPTION_KEY"),
        ),
        restore=RestoreConfig(
            verify_checksum=bool(restore.get("verify_checksum", True)),
            require_confirmation=bool(restore.get("require_confirmation", True)),
        ),
    )
