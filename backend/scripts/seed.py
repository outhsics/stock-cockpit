"""Seed script: create default admin user if none exists.

Run via:  python -m backend.scripts.seed
"""
from __future__ import annotations

import secrets
import sys

# Ensure the backend package is importable when run as a script.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.auth.service import hash_password  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.database import SessionLocal, init_db  # noqa: E402
from backend.app.models import User  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == settings.default_admin_username).first()
        if existing:
            print(f"[seed] Admin user '{existing.username}' already exists — skipping.")
            return

        password = settings.default_admin_password or secrets.token_urlsafe(12)
        user = User(
            username=settings.default_admin_username,
            hashed_password=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()

        print("=" * 60)
        print("[seed] Default admin user created.")
        print(f"  username: {user.username}")
        print(f"  password: {password}")
        print("  (Save this password. You can change it later in the app.)")
        if not settings.default_admin_password:
            print("  NOTE: password was auto-generated because")
            print("        DEFAULT_ADMIN_PASSWORD was not set in .env.")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
