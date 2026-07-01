from nxbak.checksum import read_checksums, sha256_file, write_checksums


def test_checksum_roundtrip(tmp_path):
    file = tmp_path / "database.dump.gz"
    file.write_bytes(b"backup")
    checksums = tmp_path / "checksums.sha256"
    write_checksums(checksums, [file])
    assert read_checksums(checksums)[file.name] == sha256_file(file)
