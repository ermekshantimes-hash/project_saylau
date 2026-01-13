"""
Создание пользователя с ARGON2 хешем (не bcrypt!)
"""
from argon2 import PasswordHasher
import psycopg2
from datetime import datetime

# Создать Argon2 хеш
ph = PasswordHasher()
password_hash = ph.hash("test123")

print(f"Argon2 хеш: {password_hash}\n")

# Подключиться к БД
conn = psycopg2.connect(
    dbname='elections_rk',
    user='postgres',
    password='23june1970',
    host='localhost'
)
cur = conn.cursor()

try:
    cur.execute("""
        INSERT INTO users (phone, email, username, password_hash, role, status, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            status = EXCLUDED.status,
            role = EXCLUDED.role
        RETURNING id, email, role, status
    """, (
        None,  # phone
        'test@elections.kz',
        'testuser',
        password_hash,
        'ADMIN',
        'ACTIVE',  # ВАЖНО!
        True,
        datetime.now()
    ))
    
    result = cur.fetchone()
    conn.commit()
    
    print("=" * 70)
    print("✅ ПОЛЬЗОВАТЕЛЬ СОЗДАН С ARGON2!")
    print("=" * 70)
    print(f"ID: {result[0]}")
    print(f"Email: {result[1]}")
    print(f"Роль: {result[2]}")
    print(f"Статус: {result[3]}")
    print(f"\n🔑 Учетные данные для входа:")
    print(f"   Email: test@elections.kz")
    print(f"   Пароль: test123")
    print(f"\n🚀 Откройте: http://localhost:8000/login.html")
    print("=" * 70)
    
except Exception as e:
    conn.rollback()
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
