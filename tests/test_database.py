import gzip

from nxbak.database import restore_dump


def test_restore_dump_always_uses_force_mode(monkeypatch, tmp_path):
    dump = tmp_path / "database.dump.gz"
    with gzip.open(dump, "wb") as fh:
        fh.write(b"dump")

    seen = {}
    monkeypatch.setattr("nxbak.database.require_executable", lambda _name: "pg_restore")

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["check"] = kwargs.get("check", True)

    monkeypatch.setattr("nxbak.database.run", fake_run)

    restore_dump("postgresql://secret", dump)

    assert "--exit-on-error" not in seen["args"]
    assert "--disable-triggers" in seen["args"]
    assert "--no-acl" not in seen["args"]
    assert "--no-owner" not in seen["args"]
    assert seen["check"] is False
