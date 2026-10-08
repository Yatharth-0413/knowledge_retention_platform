"""Unit tests for app/auth/security.py - password hashing and JWT issuance/validation.

These are the foundation of every authenticated endpoint in the app, so a silent
regression here (e.g. hash_password/verify_password drifting out of sync, or
decode_access_token accepting a tampered/expired token) would be a security bug,
not just a test failure.
"""

from datetime import timedelta

from freezegun import freeze_time

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_is_not_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_hash_password_is_salted_differently_each_time():
    # Two hashes of the same password must differ (bcrypt salts per-call) - if this
    # ever started returning identical hashes it would mean salting silently broke.
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second


def test_verify_password_accepts_correct_password():
    hashed = hash_password("my-secret-password")
    assert verify_password("my-secret-password", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("my-secret-password")
    assert verify_password("not-the-password", hashed) is False


def test_verify_password_rejects_garbage_hash():
    # A malformed hash (e.g. corrupted DB value) must fail closed, not raise.
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_create_and_decode_access_token_round_trip():
    token = create_access_token(subject="42", extra_claims={"role": "manager"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "manager"


def test_decode_access_token_rejects_garbage_token():
    assert decode_access_token("not.a.jwt") is None


def test_decode_access_token_rejects_expired_token():
    with freeze_time("2026-01-01 00:00:00"):
        token = create_access_token(subject="1")
    with freeze_time("2026-01-01 00:00:00") as frozen:
        # access_token_expire_minutes defaults to 1440 (24h) - jump well past it.
        frozen.move_to("2026-01-03 00:00:00")
        assert decode_access_token(token) is None
