from __future__ import annotations

import gzip
from pathlib import Path

from .utils import require_executable, run


def dump_database(database_url: str, target_gz: Path) -> None:
    require_executable("pg_dump")
    raw = target_gz.with_suffix("")
    try:
        run(["pg_dump", "--dbname", database_url, "--format=custom", "--no-password", "--file", str(raw)])
        with raw.open("rb") as src, gzip.open(target_gz, "wb") as dst:
            dst.writelines(src)
    finally:
        raw.unlink(missing_ok=True)


def check_connection(database_url: str) -> None:
    require_executable("pg_dump")
    run(["pg_dump", "--dbname", database_url, "--schema-only", "--no-password", "--file", "-"])


def restore_database(database_url: str, dump_gz: Path) -> None:
    require_executable("pg_restore")
    raw = dump_gz.with_suffix("")
    try:
        with gzip.open(dump_gz, "rb") as src, raw.open("wb") as dst:
            dst.writelines(src)
        run(["pg_restore", "--dbname", database_url, "--clean", "--if-exists", "--no-owner", "--no-password", str(raw)])
    finally:
        raw.unlink(missing_ok=True)
