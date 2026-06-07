from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .exceptions import DependencyError, NxbakError


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            check=check,
            shell=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        command = " ".join(args[:2])
        raise NxbakError(f"Command timed out after {timeout} seconds: {command}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise NxbakError(detail) from exc


def run_bytes(args: list[str], *, cwd: Path | None = None) -> bytes:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            check=True,
            shell=False,
        ).stdout
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode(errors="replace").strip() or exc.stdout.decode(errors="replace").strip() or str(exc)
        raise NxbakError(detail) from exc


def require_executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise DependencyError(f"Required executable '{name}' was not found in PATH.")
    return path


def is_env_set(name: str) -> bool:
    return bool(os.getenv(name))


def mask_secret(value: str | None) -> str:
    if not value:
        return "<unset>"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
