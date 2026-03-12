import os
import hashlib
import secrets
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    try:
        salt, key_hex = hashed.split('$', 1)
        key = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000
        )
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False
