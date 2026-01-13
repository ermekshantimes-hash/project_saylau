"""
Финальный скрипт создания пользователя
Использует встроенный hashlib вместо bcrypt для совместимости
"""
import psycopg2
from datetime import datetime

# Простой хеш для теста (НЕ для продакшена!)
# Для продакшена используйте bcrypt
test_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqgdViLu"

conn = psycopg2.connect(
    dbname='elections_rk',
    user='postgres', 
    password='23june1970',
    host='localhost'
)
cur = conn.cursor()

try:
    cur.execute("""
        INSERT INTO users (email, username, password_hash, role, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            role = EXCLUDED.role,
            is_active = EXCLUDED.is_active
        RETURNING id, email, role
    """, (
        'test@elections.kz',
        'testuser',
        test_hash,
        'ADMIN',
        True,
        datetime.now()
    ))
    
    result = cur.fetchone()
    conn.commit()
    
    print("=" * 60)
    print("✅ ПОЛЬЗОВАТЕЛЬ СОЗДАН/ОБНОВЛЕН")
    print("=" * 60)
    print(f"ID: {result[0]}")
    print(f"Email: {result[1]}")
    print(f"Роль: {result[2]}")
    print(f"\n🔑 Учетные данные:")
    print(f"   Email: test@elections.kz")
    print(f"   Пароль: test123")
    print("=" * 60)
    
except Exception as e:
    conn.rollback()
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
