"""
Create (or update) a super admin user.

Usage:
    python -m seeds.create_superadmin <email> <password> [full_name] [phone]
    python -m seeds.create_superadmin            # uses the defaults below

Idempotent: re-running with the same email resets that user's password and
re-asserts the super_admin role rather than creating a duplicate.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from database import AsyncSessionLocal

DEFAULT_EMAIL = "rhm@gmail.com"
# Never a real password: pass one on the command line, or set
# SUPERADMIN_PASSWORD. A default that works is a default that ships.
DEFAULT_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "")
DEFAULT_NAME = "Rashed — Super Admin"
DEFAULT_PHONE = "+966500000099"


async def create_superadmin(
    email: str,
    password: str,
    full_name: str = DEFAULT_NAME,
    phone: str = DEFAULT_PHONE,
) -> None:
    from auth.password import hash_password
    from models.user import User, UserRole

    async with AsyncSessionLocal() as db:
        try:
            existing = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()

            now = datetime.now(timezone.utc)
            if existing:
                existing.hashed_password = hash_password(password)
                existing.role = UserRole.SUPER_ADMIN
                existing.is_active = True
                existing.is_email_verified = True
                existing.email_verified_at = existing.email_verified_at or now
                existing.deleted_at = None
                action = "updated"
                user_id = existing.id
            else:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    phone=phone,
                    full_name=full_name,
                    hashed_password=hash_password(password),
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    is_email_verified=True,
                    email_verified_at=now,
                )
                db.add(user)
                await db.flush()
                action = "created"
                user_id = user.id

            await db.commit()
            print(f"✅ Super admin {action}: {email}  (id={user_id})")
        except Exception as exc:
            await db.rollback()
            print(f"❌ Failed: {exc}")
            raise


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2 and not DEFAULT_PASSWORD:
        print(
            "استخدم: python -m seeds.create_superadmin <البريد> <كلمة المرور>\n"
            "او اضبط SUPERADMIN_PASSWORD في البيئة."
        )
        raise SystemExit(2)
    asyncio.run(
        create_superadmin(
            args[0] if len(args) > 0 else DEFAULT_EMAIL,
            args[1] if len(args) > 1 else DEFAULT_PASSWORD,
            args[2] if len(args) > 2 else DEFAULT_NAME,
            args[3] if len(args) > 3 else DEFAULT_PHONE,
        )
    )
