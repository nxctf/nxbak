from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .backup import create_backup
from .config import load_config
from .exceptions import NxbakError
from .git import active_branch, fetch, find_repo_root, log, remote_url
from .restore import decrypt_snapshot, load_snapshot, restore_snapshot
from .utils import is_env_set, mask_secret, require_executable

app = typer.Typer(no_args_is_help=True, help="NXBAK Git-backed Supabase backup CLI")
console = Console()


def context():
    repo_root = find_repo_root()
    load_dotenv(repo_root / ".env", override=False)
    config = load_config(repo_root)
    remote_url(repo_root, config.remote)
    return repo_root, config


def handle_error(exc: Exception) -> None:
    message = str(exc)
    for key in ("NXBAK_SUPABASE_DB_URL", "NXBAK_ENCRYPTION_KEY"):
        message = message.replace(os.getenv(key, ""), "***") if os.getenv(key) else message
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


@app.command()
def backup(
    daily: bool = typer.Option(False, "--daily", help="Write to snapshots/daily"),
    monthly: bool = typer.Option(False, "--monthly", help="Write to snapshots/monthly"),
):
    try:
        repo_root, config = context()
        result = create_backup(repo_root, config, snapshot_type=config.type_for(daily=daily, monthly=monthly))
    except Exception as exc:
        handle_error(exc)
    console.print("\n[bold green]NXBAK backup completed[/bold green]\n")
    for label, value in result.items():
        console.print(f"{label.title()}: {value}")


@app.command("list")
def list_snapshots(
    daily: bool = typer.Option(False, "--daily", help="Read snapshots/daily"),
    monthly: bool = typer.Option(False, "--monthly", help="Read snapshots/monthly"),
    limit: int = typer.Option(10, "--limit", min=1),
):
    try:
        repo_root, config = context()
        if daily or monthly:
            kinds = [config.type_for(daily=daily, monthly=monthly)]
        else:
            kinds = config.snapshot_types()
        rows = []
        for kind in kinds:
            try:
                for row in log(repo_root, config.remote, config.branch_for_type(kind), limit):
                    rows.append({"type": kind, "branch": config.branch_for_type(kind), **row})
            except Exception:
                continue
    except Exception as exc:
        handle_error(exc)
    table = Table()
    table.add_column("TYPE")
    table.add_column("BRANCH")
    table.add_column("COMMIT")
    table.add_column("CREATED")
    table.add_column("MESSAGE")
    for row in rows:
        table.add_row(row["type"], row["branch"], row["commit"], row["created"], row["message"])
    console.print(table)


@app.command()
def restore(
    daily: bool = typer.Option(False, "--daily", help="Restore from snapshots/daily"),
    monthly: bool = typer.Option(False, "--monthly", help="Restore from snapshots/monthly"),
    commit: str | None = typer.Option(None, "--commit", help="Restore a specific snapshot commit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate restore without changing database"),
    yes: bool = typer.Option(False, "--yes", help="Skip interactive confirmation"),
):
    try:
        repo_root, config = context()
        snapshot_type = config.type_for(daily=daily, monthly=monthly)
        if not dry_run and not yes and config.restore.require_confirmation:
            selected_commit, manifest, _, tmp_ctx = load_snapshot(repo_root, config, snapshot_type=snapshot_type, commit=commit)
            try:
                console.print("You are about to restore a database.\n")
                console.print(f"Type: {manifest['backup_type']}")
                console.print(f"Commit: {selected_commit[:7]}")
                console.print(f"Created: {manifest['created_at']}")
                console.print(f"Target: {config.source.database_url_env}")
                typed = typer.prompt("Type RESTORE to continue")
                if typed != "RESTORE":
                    raise NxbakError("Restore cancelled.")
            finally:
                tmp_ctx.cleanup()
        elif yes and not dry_run:
            console.print("[yellow]Warning: --yes skips restore confirmation.[/yellow]")
        result = restore_snapshot(repo_root, config, snapshot_type=snapshot_type, commit=commit, dry_run=dry_run)
    except Exception as exc:
        handle_error(exc)
    console.print("\n[bold green]NXBAK restore check completed[/bold green]" if dry_run else "\n[bold green]NXBAK restore completed[/bold green]")
    for label, value in result.items():
        console.print(f"{label.title()}: {value}")


@app.command()
def status():
    try:
        repo_root, config = context()
        url = remote_url(repo_root, config.remote)
    except Exception as exc:
        handle_error(exc)
    table = Table(show_header=False)
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("Repository root", str(repo_root))
    table.add_row("Remote", config.remote)
    table.add_row("Remote URL", mask_secret(url))
    table.add_row("Active branch", active_branch(repo_root))
    table.add_row("Manual branch", config.branches.manual)
    table.add_row("Daily branch", config.branches.daily)
    table.add_row("Monthly branch", config.branches.monthly)
    table.add_row(config.source.database_url_env, "set" if is_env_set(config.source.database_url_env) else "missing")
    table.add_row(config.backup.encryption_key_env, "set" if is_env_set(config.backup.encryption_key_env) else "missing")
    for exe in ("git", "pg_dump", "pg_restore"):
        try:
            require_executable(exe)
            value = "available"
        except Exception:
            value = "missing"
        table.add_row(exe, value)
    console.print(table)


@app.command()
def doctor(remote_check: bool = typer.Option(False, "--remote-check", help="Also run git fetch against the configured remote")):
    failed = False
    try:
        repo_root, config = context()
        remote_url(repo_root, config.remote)
        checks = [
            ("config", True),
            (f"remote {config.remote}", True),
            (config.source.database_url_env, is_env_set(config.source.database_url_env)),
            (config.backup.encryption_key_env, (not config.backup.encryption) or is_env_set(config.backup.encryption_key_env)),
        ]
        if remote_check:
            fetch(repo_root, config.remote)
            checks.append((f"git fetch {config.remote}", True))
    except Exception as exc:
        handle_error(exc)
    for exe in ("git", "pg_dump", "pg_restore"):
        try:
            require_executable(exe)
            checks.append((exe, True))
        except Exception:
            checks.append((exe, False))
    for name, ok in checks:
        failed = failed or not ok
        console.print(f"{'[OK]' if ok else '[FAIL]'} {name}")
    if failed:
        raise typer.Exit(1)


@app.command()
def inspect(
    commit: str = typer.Option(..., "--commit", help="Snapshot commit"),
    daily: bool = typer.Option(False, "--daily"),
    monthly: bool = typer.Option(False, "--monthly"),
):
    try:
        repo_root, config = context()
        _, manifest, _, tmp_ctx = load_snapshot(repo_root, config, snapshot_type=config.type_for(daily=daily, monthly=monthly), commit=commit)
        tmp_ctx.cleanup()
    except Exception as exc:
        handle_error(exc)
    console.print(json.dumps(manifest, indent=2))


@app.command()
def decrypt(
    commit: str = typer.Option(..., "--commit", help="Snapshot commit to decrypt"),
    daily: bool = typer.Option(False, "--daily", help="Read snapshots/daily"),
    monthly: bool = typer.Option(False, "--monthly", help="Read snapshots/monthly"),
    out: Path = typer.Option(Path("nxbak-decrypted"), "--out", help="Output directory"),
):
    try:
        repo_root, config = context()
        result = decrypt_snapshot(repo_root, config, snapshot_type=config.type_for(daily=daily, monthly=monthly), commit=commit, output_dir=out)
    except Exception as exc:
        handle_error(exc)
    console.print("\n[bold green]NXBAK snapshot decrypted[/bold green]\n")
    for label, value in result.items():
        console.print(f"{label.title()}: {value}")


if __name__ == "__main__":
    app()
