"""Create or update a demo admin user for local login.

This script matches the current ORM schema (app.models_extended.User) and uses
the same password hashing implementation as the API (app.auth_utils.hash_password).
"""

from app.database import SessionLocal
from app.auth_utils import hash_password
from app.models_extended import User, UserRole


def create_test_user() -> None:
    email = "test@elections.kz"
    password = "test123"

    db = SessionLocal()
    try:
        print("🔧 Создание тестового пользователя...\n")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                phone=None,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                status="ACTIVE",
                mfa_enabled=False,
                mfa_secret=None,
            )
            db.add(user)
        else:
            user.password_hash = hash_password(password)
            user.role = UserRole.ADMIN
            user.status = "ACTIVE"

        db.commit()
        db.refresh(user)

        print("=" * 70)
        print("✅ ТЕСТОВЫЙ ПОЛЬЗОВАТЕЛЬ ГОТОВ!")
        print("=" * 70)
        print(f"\n👤 ID: {user.id}")
        print(f"📧 Email: {email}")
        print(f"🔑 Пароль: {password}")
        print(f"👑 Роль: ADMIN")
        print(f"\n🚀 Откройте: http://127.0.0.1:8001/login.html")
        print("   Введите email и пароль для входа")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    create_test_user()
