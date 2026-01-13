-- SQL для создания тестового пользователя
-- Пароль: test123
-- Хеш создан с помощью bcrypt

INSERT INTO users (email, username, password_hash, role, is_active, created_at)
VALUES (
    'test@elections.kz',
    'testuser',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqgdViLu',
    'ADMIN',
    true,
    NOW()
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active;
