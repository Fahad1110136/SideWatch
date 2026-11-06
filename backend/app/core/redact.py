SENSITIVE_PARTS = ("password", "passwd", "token", "secret", "csrf", "hash",
                   "authorization", "cookie", "api_key")
MAX_STR = 200


def redact(value, _key: str = ""):
    """Mask sensitive keys and truncate long strings before anything is logged."""
    if any(part in _key.lower() for part in SENSITIVE_PARTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, _key) for v in value]
    if isinstance(value, str):
        return value[:MAX_STR]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:MAX_STR]