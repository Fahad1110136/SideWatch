from backend.app.core.redact import redact


def test_sensitive_keys_masked_even_nested():
    out = redact({"user": "a", "password": "p", "meta": {"session_token": "t", "ok": 1}})
    assert out["password"] == "[REDACTED]"
    assert out["meta"]["session_token"] == "[REDACTED]"
    assert out["user"] == "a" and out["meta"]["ok"] == 1


def test_long_strings_truncated():
    assert len(redact({"note": "x" * 1000})["note"]) == 200


def test_unusual_types_become_strings():
    assert isinstance(redact({"v": object()})["v"], str)