"""Seed script: default categories + demo users (admin/officer/citizen)."""

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Category, User
from app.security import hash_password

CATEGORIES = [
    ("Roads & Potholes", "roads", "🛣️", 7),
    ("Street Lights", "streetlights", "💡", 4),
    ("Garbage & Sanitation", "garbage", "🗑️", 5),
    ("Water Supply", "water", "🚰", 6),
    ("Sewage & Drainage", "sewage", "🌊", 8),
    ("Parks & Public Spaces", "parks", "🌳", 2),
    ("Electricity", "electricity", "⚡", 6),
    ("Other", "other", "📌", 1),
]

USERS = [
    ("Admin Karachi", "admin@shikayat.pk", "admin12345", "admin", "Karachi Central"),
    ("Officer Gulshan", "officer@shikayat.pk", "officer123", "officer", "Gulshan-e-Iqbal"),
    ("Officer Saddar", "saddar@shikayat.pk", "officer123", "officer", "Saddar"),
    ("Demo Citizen", "citizen@shikayat.pk", "citizen123", "citizen", None),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for name, slug, icon, bp in CATEGORIES:
            if db.scalar(select(Category).where(Category.slug == slug)) is None:
                db.add(Category(name=name, slug=slug, icon=icon, base_priority=bp))

        for name, email, pw, role, ward in USERS:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(name=name, email=email, password_hash=hash_password(pw), role=role, ward=ward))
        db.commit()
        print("Seeded categories and demo users.")
        print("  admin@shikayat.pk / admin12345")
        print("  officer@shikayat.pk / officer123")
        print("  citizen@shikayat.pk / citizen123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
