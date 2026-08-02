from app.core.security import hash_password, verify_password


def test_password_hash_round_trip() -> None:
    hashed = hash_password("correct-password")

    assert verify_password("correct-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_unknown_legacy_hash_is_an_invalid_password() -> None:
    assert verify_password("any-password", "legacy-plain-text") is False
    assert verify_password("any-password", "") is False
