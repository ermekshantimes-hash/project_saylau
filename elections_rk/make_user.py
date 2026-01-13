import psycopg2
import bcrypt

conn = psycopg2.connect(dbname='elections_rk', user='postgres', password='23june1970', host='localhost')
cur = conn.cursor()

# Генерируем правильный хеш
password_hash = bcrypt.hashpw(b'test123', bcrypt.gensalt()).decode()

# Создаем пользователя
cur.execute("""
    INSERT INTO users (email, username, password_hash, role, is_active, created_at)
    VALUES (%s, %s, %s, %s, %s, NOW())
    ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        role = EXCLUDED.role
    RETURNING id
""", ("test@elections.kz", "testuser", password_hash, "ADMIN", True))

user_id = cur.fetchone()[0]
conn.commit()

print(f"✅ Пользователь создан/обновлен (ID: {user_id})")
print(f"Email: test@elections.kz")
print(f"Password: test123")
print(f"Hash: {password_hash}")

conn.close()
