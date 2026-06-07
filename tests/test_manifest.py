from nxbak.manifest import create_manifest


def test_create_manifest(tmp_path):
    backup = tmp_path / "database.dump.gz.enc"
    backup.write_bytes(b"secret")
    manifest = create_manifest(backup_type="manual", encrypted=True, backup_files=[backup], created_at="2026-06-07T02:00:00Z")
    assert manifest["tool"] == "nxbak"
    assert manifest["backup_type"] == "manual"
    assert manifest["encrypted"] is True
    assert manifest["files"][0]["name"] == "database.dump.gz.enc"
