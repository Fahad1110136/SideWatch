import logging

from backend.app.config import Settings

logger = logging.getLogger("sidewatch")
PLACEHOLDER_KEYS = {"", "change-me", "change-me-to-a-long-random-string"}
MIN_KEY_LENGTH = 32


# def find_problems(s: Settings) -> list[str]:
#     problems = []
#     if s.secret_key in PLACEHOLDER_KEYS or len(s.secret_key) < MIN_KEY_LENGTH:
#         problems.append(f"SECRET_KEY is a placeholder or shorter than {MIN_KEY_LENGTH} characters.")
#     return problems

def find_problems(s: Settings) -> list[str]:
    problems = []
    weak = (s.secret_key in PLACEHOLDER_KEYS
            or s.secret_key.startswith(("change-me", "replace-with"))
            or len(s.secret_key) < MIN_KEY_LENGTH)
    if weak:
        problems.append(f"SECRET_KEY is a placeholder or shorter than {MIN_KEY_LENGTH} characters.")
    return problems


def enforce_secure_settings(s: Settings) -> list[str]:
    """Production refuses to start with an insecure config; development only warns."""
    problems = find_problems(s)
    if problems and s.app_env == "production":
        raise RuntimeError("Refusing to start in production: " + " ".join(problems))
    for p in problems:
        logger.warning("Insecure setting: %s", p)
    return problems