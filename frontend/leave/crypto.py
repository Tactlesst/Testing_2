from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings



def _get_fernet() -> Fernet:
    key = settings.FERNET_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_text(plaintext: str) -> bytes:
    if plaintext is None:
        return None
    f = _get_fernet()
    return f.encrypt(plaintext.encode())  


def decrypt_text(token: bytes) -> str | None:
    if not token:
        return None
    f = _get_fernet()
    try:
        return f.decrypt(token).decode()
    except InvalidToken:
        return None
