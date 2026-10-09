import hashlib

from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("dummy-password-never-used")
COOKIE = "opspilot_session"


def session_key(token: str) -> str:
    return "session:" + hashlib.sha256(token.encode()).hexdigest()
