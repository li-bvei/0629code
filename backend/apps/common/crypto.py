from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_text(value):
    if value in (None, ''):
        return value
    return _fernet().encrypt(str(value).encode()).decode()


def decrypt_text(value):
    """Decrypt a value; if it isn't a valid token (e.g. legacy plaintext
    that hasn't been migrated yet), return it unchanged."""
    if value in (None, ''):
        return value
    try:
        return _fernet().decrypt(str(value).encode()).decode()
    except (InvalidToken, ValueError):
        return value
