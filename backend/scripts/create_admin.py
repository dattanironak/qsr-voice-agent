"""Create or reset an admin login for the /admin dashboard.

Usage:
    python scripts/create_admin.py <username> [--role owner]

Prompts for a password (hidden input), then upserts an admin_users row by username —
safe to re-run against an existing username to reset its password or role.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.auth import ADMIN_ROLES, hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AdminUser  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("--role", default="owner")
    args = parser.parse_args()

    if args.role not in ADMIN_ROLES:
        print(f"--role must be one of {', '.join(ADMIN_ROLES)}")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match")
        sys.exit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters")
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.execute(
            select(AdminUser).where(AdminUser.username == args.username)
        ).scalar_one_or_none()
        if user is None:
            user = AdminUser(username=args.username, role=args.role, password_hash=hash_password(password))
            db.add(user)
            action = "Created"
        else:
            user.password_hash = hash_password(password)
            user.role = args.role
            action = "Updated"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"{action} admin user '{args.username}' (role: {args.role})")


if __name__ == "__main__":
    main()
