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


def run_query(database_url: str, query: str) -> list[str]:
    """Execute a query via psql and return the results as a list of trimmed strings."""
    require_executable("psql")
    res = run(
        [
            "psql",
            "--dbname",
            database_url,
            "--no-password",
            "--tuples-only",
            "--no-align",
            "--command",
            query,
        ],
        timeout=60,
    )
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def execute_sql(database_url: str, sql: str) -> None:
    """Execute arbitrary SQL statements via psql."""
    require_executable("psql")
    run(
        [
            "psql",
            "--dbname",
            database_url,
            "--no-password",
            "--command",
            sql,
        ],
        timeout=120,
    )


def get_extensions(database_url: str) -> list[dict[str, str]]:
    """Get active extensions and their schemas, excluding standard postgres metadata."""
    query = "SELECT extname, extnamespace::regnamespace::text FROM pg_extension WHERE extname != 'plpgsql';"
    try:
        lines = run_query(database_url, query)
        extensions = []
        for line in lines:
            if "|" in line:
                name, schema = line.split("|", 1)
                extensions.append({"name": name.strip(), "schema": schema.strip()})
            else:
                extensions.append({"name": line.strip(), "schema": "public"})
        return extensions
    except Exception:
        return []


def get_realtime_tables(database_url: str) -> list[str]:
    """Get list of tables that have realtime replication enabled (in 'supabase_realtime' publication)."""
    check_query = "SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime';"
    try:
        exists = run_query(database_url, check_query)
        if not exists:
            return []
        
        query = (
            "SELECT n.nspname || '.' || c.relname "
            "FROM pg_publication_rel pr "
            "JOIN pg_publication p ON p.oid = pr.prpubid "
            "JOIN pg_class c ON c.oid = pr.prrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE p.pubname = 'supabase_realtime';"
        )
        return run_query(database_url, query)
    except Exception:
        return []
