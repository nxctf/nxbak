from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .exceptions import GitError
from .utils import require_executable, run, run_bytes


def find_repo_root(start: Path | None = None) -> Path:
    require_executable("git")
    current = (start or Path.cwd()).resolve()
    for path in [current, *current.parents]:
        if (path / ".git").exists():
            return path
    raise GitError("NXBAK repository not detected.\nRun NXBAK inside the cloned repository.")


def remote_url(repo_root: Path, remote: str = "origin") -> str:
    try:
        return run(["git", "remote", "get-url", remote], cwd=repo_root).stdout.strip()
    except Exception as exc:
        raise GitError(f"Git remote '{remote}' was not found.\nConfigure it using:\ngit remote add {remote} <url>") from exc


def active_branch(repo_root: Path) -> str:
    return run(["git", "branch", "--show-current"], cwd=repo_root).stdout.strip() or "(detached)"


def fetch(repo_root: Path, remote: str, branch: str | None = None) -> None:
    args = ["git", "fetch", remote]
    if branch:
        args.append(branch)
    run(args, cwd=repo_root)


def branch_exists(repo_root: Path, remote: str, branch: str) -> bool:
    result = run(["git", "ls-remote", "--heads", remote, branch], cwd=repo_root)
    return bool(result.stdout.strip())


def ensure_snapshot_branch(repo_root: Path, remote: str, branch: str) -> None:
    fetch(repo_root, remote)
    if branch_exists(repo_root, remote, branch):
        return
    with tempfile.TemporaryDirectory(prefix="nxbak-init-") as tmp:
        worktree = Path(tmp) / "worktree"
        run(["git", "worktree", "add", "--detach", str(worktree)], cwd=repo_root)
        try:
            run(["git", "checkout", "--orphan", branch], cwd=worktree)
            for item in worktree.iterdir():
                if item.name == ".git":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            (worktree / ".gitkeep").write_text("", encoding="utf-8")
            run(["git", "add", ".gitkeep"], cwd=worktree)
            run(["git", "commit", "-m", "Initialize NXBAK snapshot branch"], cwd=worktree)
            run(["git", "push", remote, f"HEAD:{branch}"], cwd=worktree)
        finally:
            run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root)


@contextmanager
def snapshot_worktree(repo_root: Path, remote: str, branch: str):
    ensure_snapshot_branch(repo_root, remote, branch)
    fetch(repo_root, remote, branch)
    tmp = tempfile.TemporaryDirectory(prefix="nxbak-worktree-")
    worktree = Path(tmp.name) / "snapshot"
    try:
        run(["git", "worktree", "add", str(worktree), f"{remote}/{branch}"], cwd=repo_root)
        yield worktree
    finally:
        run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root)
        tmp.cleanup()


def replace_snapshot_files(worktree: Path, files: list[Path], message: str, remote: str, branch: str) -> str:
    for item in worktree.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    for file in files:
        shutil.copy2(file, worktree / file.name)
    run(["git", "add", "-A"], cwd=worktree)
    run(["git", "commit", "-m", message], cwd=worktree)
    for _ in range(2):
        try:
            run(["git", "push", remote, f"HEAD:{branch}"], cwd=worktree)
            return run(["git", "rev-parse", "--short", "HEAD"], cwd=worktree).stdout.strip()
        except Exception:
            run(["git", "fetch", remote, branch], cwd=worktree)
            run(["git", "rebase", f"{remote}/{branch}"], cwd=worktree)
    raise GitError("Unable to push snapshot without force. Remote branch changed; retry later.")


def log(repo_root: Path, remote: str, branch: str, limit: int) -> list[dict[str, str]]:
    fetch(repo_root, remote, branch)
    fmt = "%h%x09%ci%x09%s"
    out = run(["git", "log", f"{remote}/{branch}", f"--max-count={limit}", f"--format={fmt}"], cwd=repo_root).stdout
    rows = []
    for line in out.splitlines():
        commit, created, message = line.split("\t", 2)
        if message == "Initialize NXBAK snapshot branch":
            continue
        rows.append({"commit": commit, "created": created, "message": message})
    return rows


def latest_commit(repo_root: Path, remote: str, branch: str) -> str:
    fetch(repo_root, remote, branch)
    return run(["git", "rev-parse", f"{remote}/{branch}"], cwd=repo_root).stdout.strip()


def commit_in_branch(repo_root: Path, remote: str, branch: str, commit: str) -> bool:
    fetch(repo_root, remote, branch)
    try:
        run(["git", "merge-base", "--is-ancestor", commit, f"{remote}/{branch}"], cwd=repo_root)
        return True
    except Exception:
        return False


def show_file(repo_root: Path, commit: str, path: str, target: Path) -> None:
    data = run(["git", "show", f"{commit}:{path}"], cwd=repo_root).stdout
    target.write_text(data, encoding="utf-8")


def show_binary_file(repo_root: Path, commit: str, path: str, target: Path) -> None:
    target.write_bytes(run_bytes(["git", "show", f"{commit}:{path}"], cwd=repo_root))
