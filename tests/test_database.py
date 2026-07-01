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


def test_run_query(monkeypatch):
    seen = {}
    monkeypatch.setattr("nxbak.database.require_executable", lambda _name: "psql")
    
    class FakeProcess:
        stdout = "row1\nrow2\n"
        
    def fake_run(args, **kwargs):
        seen["args"] = args
        return FakeProcess()
        
    monkeypatch.setattr("nxbak.database.run", fake_run)
    
    from nxbak.database import run_query
    res = run_query("postgresql://secret", "SELECT 1;")
    assert res == ["row1", "row2"]
    assert "psql" in seen["args"]
    assert "SELECT 1;" in seen["args"]


def test_execute_sql(monkeypatch):
    seen = {}
    monkeypatch.setattr("nxbak.database.require_executable", lambda _name: "psql")
    
    def fake_run(args, **kwargs):
        seen["args"] = args
        return None
        
    monkeypatch.setattr("nxbak.database.run", fake_run)
    
    from nxbak.database import execute_sql
    execute_sql("postgresql://secret", "CREATE TABLE x;")
    assert "CREATE TABLE x;" in seen["args"]


def test_get_extensions(monkeypatch):
    monkeypatch.setattr("nxbak.database.require_executable", lambda _name: "psql")
    
    def fake_run_query(database_url, query):
        return ["uuid-ossp|extensions", "pgcrypto|extensions", "some_ext"]
        
    monkeypatch.setattr("nxbak.database.run_query", fake_run_query)
    
    from nxbak.database import get_extensions
    res = get_extensions("postgresql://secret")
    assert res == [
        {"name": "uuid-ossp", "schema": "extensions"},
        {"name": "pgcrypto", "schema": "extensions"},
        {"name": "some_ext", "schema": "public"},
    ]


def test_get_realtime_tables(monkeypatch):
    monkeypatch.setattr("nxbak.database.require_executable", lambda _name: "psql")
    
    queries = []
    def fake_run_query(database_url, query):
        queries.append(query)
        if "pg_publication_rel" in query:
            return ["public.solves", "public.notifications"]
        return ["1"]
        
    monkeypatch.setattr("nxbak.database.run_query", fake_run_query)
    
    from nxbak.database import get_realtime_tables
    res = get_realtime_tables("postgresql://secret")
    assert res == ["public.solves", "public.notifications"]
    assert len(queries) == 2
