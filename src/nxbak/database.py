from __future__ import annotations

import gzip
from pathlib import Path

from .utils import require_executable, run


def schema_args(schemas: tuple[str, ...]) -> list[str]:
    args: list[str] = []
    for schema in schemas:
        args.extend(["--schema", schema])
    return args


def table_args(tables: tuple[str, ...]) -> list[str]:
    args: list[str] = []
    for table in tables:
        args.extend(["--table", table])
    return args


def _pg_dump_gz(database_url: str, target_gz: Path, extra_args: list[str]) -> None:
    """Run pg_dump with extra_args, compress result to target_gz."""
    raw = target_gz.with_suffix("")
    try:
        run(
            [
                "pg_dump",
                "--dbname",
                database_url,
                "--format=custom",
                "--no-password",
                *extra_args,
                "--file",
                str(raw),
            ],
            timeout=1200,
        )
        with raw.open("rb") as src, gzip.open(target_gz, "wb") as dst:
            dst.writelines(src)
    finally:
        raw.unlink(missing_ok=True)


def dump_schema(database_url: str, target_gz: Path, schemas: tuple[str, ...]) -> None:
    """Dump full schema objects: tables, data, triggers, functions, sequences, ACLs, etc."""
    require_executable("pg_dump")
    _pg_dump_gz(database_url, target_gz, schema_args(schemas))


def dump_auth_tables(database_url: str, target_gz: Path, tables: tuple[str, ...]) -> None:
    """Dump auth tables (structure + data) separately from schemas."""
    require_executable("pg_dump")
    _pg_dump_gz(database_url, target_gz, table_args(tables))


def check_connection(database_url: str) -> None:
    require_executable("pg_dump")
    run(["pg_dump", "--dbname", database_url, "--schema-only", "--no-password", "--file", "-"], timeout=120)


def _pg_restore(database_url: str, dump_gz: Path) -> None:
    """Run pg_restore on a gzipped custom-format dump. Always force mode."""
    require_executable("pg_restore")
    raw = dump_gz.with_suffix("")
    try:
        with gzip.open(dump_gz, "rb") as src, raw.open("wb") as dst:
            dst.writelines(src)
        run(
            [
                "pg_restore",
                "--dbname",
                database_url,
                "--clean",
                "--if-exists",
                "--no-password",
                "--disable-triggers",
                str(raw),
            ],
            timeout=1200,
            check=False,
        )
    finally:
        raw.unlink(missing_ok=True)


def restore_dump(database_url: str, dump_gz: Path) -> None:
    """Restore a single gzipped custom-format dump file. Always force mode."""
    _pg_restore(database_url, dump_gz)
