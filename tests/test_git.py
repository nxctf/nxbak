from pathlib import Path

from nxbak.git import find_repo_root, log, remote_url
from nxbak.utils import run


def test_find_repo_root_and_remote(tmp_path: Path):
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    run(["git", "init", "--bare", str(remote)])
    repo.mkdir()
    run(["git", "init"], cwd=repo)
    run(["git", "remote", "add", "origin", str(remote)], cwd=repo)
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == repo.resolve()
    assert remote_url(repo, "origin") == str(remote)


def test_log_hides_initializer_commit(monkeypatch, tmp_path: Path):
    class Result:
        stdout = (
            "abc1234\t2026-06-07 09:00:00 +0000\tNXBAK manual snapshot: 2026-06-07T09:00:00Z\n"
            "def5678\t2026-06-07 08:59:00 +0000\tInitialize NXBAK snapshot branch\n"
        )

    monkeypatch.setattr("nxbak.git.fetch", lambda *_: None)
    monkeypatch.setattr("nxbak.git.run", lambda *_args, **_kwargs: Result())
    rows = log(tmp_path, "origin", "snapshots/manual", 10)
    assert rows == [
        {
            "commit": "abc1234",
            "created": "2026-06-07 09:00:00 +0000",
            "message": "NXBAK manual snapshot: 2026-06-07T09:00:00Z",
        }
    ]
