from pathlib import Path

from nxbak.git import find_repo_root, remote_url
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
