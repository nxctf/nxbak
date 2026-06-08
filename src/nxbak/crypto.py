from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import NxbakError

MAGIC = b"NXBAK1"
SALT_SIZE = 16
ITERATIONS = 390000


def _fernet(secret: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8"))))


def encrypt_file(source: Path, target: Path, secret: str) -> None:
    salt = os.urandom(SALT_SIZE)
    encrypted = _fernet(secret, salt).encrypt(source.read_bytes())
    target.write_bytes(MAGIC + salt + encrypted)


def decrypt_file(source: Path, target: Path, secret: str) -> None:
    data = source.read_bytes()
    if not data.startswith(MAGIC) or len(data) <= len(MAGIC) + SALT_SIZE:
        raise NxbakError("Encrypted backup file has an invalid NXBAK header.")
    salt = data[len(MAGIC): len(MAGIC) + SALT_SIZE]
    token = data[len(MAGIC) + SALT_SIZE:]
    try:
        target.write_bytes(_fernet(secret, salt).decrypt(token))
    except InvalidToken as exc:
        raise NxbakError("Unable to decrypt backup. Check NXBAK_ENCRYPTION_KEY.") from exc
