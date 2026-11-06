from backend.app.core.security import (
    constant_time_equal, generate_token, hash_password, hash_token,
    password_needs_rehash, verify_password,
)


def test_password_roundtrip():
    h = hash_password("CorrectHorse123")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "CorrectHorse123")


def test_wrong_password_rejected():
    assert not verify_password(hash_password("CorrectHorse123"), "wrong")


def test_same_password_gives_different_hashes():
    assert hash_password("CorrectHorse123") != hash_password("CorrectHorse123")


def test_garbage_hash_is_false_not_exception():
    assert verify_password("not-a-hash", "whatever") is False


def test_fresh_hash_does_not_need_rehash():
    assert not password_needs_rehash(hash_password("CorrectHorse123"))


def test_tokens_unique_and_long():
    a, b = generate_token(), generate_token()
    assert a != b and len(a) >= 40


def test_token_hash_is_stable_and_not_raw():
    t = generate_token()
    assert hash_token(t) == hash_token(t) and hash_token(t) != t


def test_constant_time_equal():
    assert constant_time_equal("abc", "abc")
    assert not constant_time_equal("abc", "abd")