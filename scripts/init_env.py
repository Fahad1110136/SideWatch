"""Create a local .env with a random secret, preserving existing configuration."""

from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]


def initialize(directory=ROOT):
    target = directory / ".env"
    # Exclusive creation keeps an existing secret and database configuration intact.
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(
                f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
                "APP_ENV=development\n"
                "DATABASE_URL=sqlite:///./data/sidewatch.db\n"
                "SESSION_TTL_MINUTES=30\n"
                "MAX_BODY_BYTES=65536\n"
            )
    except FileExistsError:
        return False
    return True


def main():
    if initialize():
        print("Created .env with a generated secret. Keep this file private.")
    else:
        print("Existing .env preserved, including its secret and database settings.")


if __name__ == "__main__":
    main()
