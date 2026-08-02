from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    try:
        return password_hash.verify(
            plain_password,
            hashed_password,
        )
    except (UnknownHashError, ValueError):
        # Treat legacy/corrupt hashes as invalid credentials instead of
        # exposing an internal error from the login endpoint.
        return False
