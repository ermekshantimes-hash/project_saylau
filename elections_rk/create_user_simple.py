"""
Создание тестового пользователя напрямую через SQL
"""

import psycopg2
from datetime import datetime

# Параметры подключения
DB_PARAMS = {
    "dbname": "elections_rk",
    "user": "postgres",
    "password": "23june1970",
    "host": "localhost",
    "port": "5432"
}

# Предрасчитанный хеш для пароля "test123"
PASSWORD_HASH = "$2b$12$nVJlXl.tMnCiP2pLcGJH3uZzGQzV5YY7H2OvXBQg4QxqJGkM/R42K"

def create_user_simple():
    """Создать пользователя напрямую"""
    
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    try:
        print("🔧 Создание тестового пользователя...\n")
        
        # Создаем пользователя
        cur.execute("""
            INSERT INTO users (email, username, password_hash, role, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                role = EXCLUDED.role,
                is_active = EXCLUDED.is_active
            RETURNING id
        """, (
            "test@elections.kz",
            "testuser",  
            PASSWORD_HASH,
            "ADMIN",
            True,
            datetime.now()
        ))
        
        user_id = cur.fetchone()[0]
        conn.commit()
        
        print("=" * 70)
        print("✅ ГОТОВО!")
        print("=" * 70)
        print(f"\n👤 Пользователь создан (ID: {user_id})")
        print(f"📧 Email: test@elections.kz")
        print(f"🔑 Пароль: test123")
        print(f"👑 Роль: ADMIN")
        print(f"\n🚀 Откройте: http://localhost:8000/login.html")
        print("=" * 70)
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_user_simple()
