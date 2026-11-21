from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    key = settings.PASSWORD_VIEW_KEY
    return Fernet(key.encode()) if key else None


def encrypt(text):
    f = _fernet()
    return f.encrypt(text.encode()).decode() if f else ''


def decrypt(token):
    f = _fernet()
    if not f or not token:
        return ''
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        return ''