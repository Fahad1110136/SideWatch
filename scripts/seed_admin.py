import argparse
import getpass
import sys

from pydantic import ValidationError

from backend.app.core.enums import AuditOutcome, Role
from backend.app.database import SessionLocal, init_db
from backend.app.repositories import audit_repo, rule_repo, user_repo
from backend.app.schemas.auth import UserCreate


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first SideWatch admin.")
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    password = getpass.getpass("Admin password (12+ chars, letters and digits): ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    try:
        data = UserCreate(username=args.username, password=password, role=Role.ADMIN)
    except ValidationError:
        sys.exit("Invalid username (3-32 chars: letters, digits, _ . -) or weak password.")

    init_db()
    with SessionLocal() as db:
        rule_repo.seed_defaults(db)
        try:
            user = user_repo.create_user(db, data.username, data.password, data.role)
        except user_repo.UsernameTaken:
            sys.exit("That username already exists.")
        audit_repo.append_event(db, "admin.seed", AuditOutcome.SUCCESS, actor_id=user.id,
                                actor_role="admin", resource_type="user", resource_id=user.id)
    print(f"Admin '{data.username}' created. Database: data/sidewatch.db")


if __name__ == "__main__":
    main()