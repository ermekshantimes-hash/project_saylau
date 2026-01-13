# Утилиты для аутентификации и безопасности
# Argon2id для паролей (с поддержкой legacy bcrypt), JWT для токенов, TOTP для MFA

from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import pyotp
import secrets
import hashlib


# Конфигурация Argon2id (по спецификации)
ARGON2_TIME_COST = 2
ARGON2_MEMORY_COST = 65536  # 64 МБ
ARGON2_PARALLELISM = 4

# Passlib context: prefer Argon2 for new hashes, but verify legacy bcrypt too.
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__time_cost=ARGON2_TIME_COST,
    argon2__memory_cost=ARGON2_MEMORY_COST,
    argon2__parallelism=ARGON2_PARALLELISM,
    argon2__salt_size=16,
)

# JWT секрет (в продакшене - из env!)
JWT_SECRET = "CHANGE_THIS_IN_PRODUCTION_TO_RANDOM_256_BIT_KEY"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRY = timedelta(hours=1)
JWT_REFRESH_EXPIRY = timedelta(days=30)


def hash_password(password: str) -> str:
    """
    Хеширование пароля через Argon2id
    """
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Проверка пароля
    """
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta = JWT_ACCESS_EXPIRY) -> str:
    """
    Создание JWT access token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict, expires_delta: timedelta = JWT_REFRESH_EXPIRY) -> str:
    """
    Создание JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Декодирование JWT токена
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def generate_mfa_secret() -> str:
    """
    Генерация секрета для TOTP (Google Authenticator)
    """
    return pyotp.random_base32()


def generate_totp_uri(secret: str, user_email: str, issuer: str = "Elections KZ") -> str:
    """
    Генерация URI для QR-кода TOTP
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=user_email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """
    Проверка TOTP кода
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # ±30 секунд


def generate_qr_token(precinct_id: int, observer_id: int, expires_hours: int = 24) -> str:
    """
    Генерация JWT токена для QR чек-ина
    """
    data = {
        "precinct_id": precinct_id,
        "observer_id": observer_id,
        "purpose": "checkin"
    }
    return create_access_token(data, expires_delta=timedelta(hours=expires_hours))


def hash_file(file_bytes: bytes) -> str:
    """
    SHA256 хеш для файлов (селфи, протоколы)
    """
    return hashlib.sha256(file_bytes).hexdigest()


def generate_audit_hash(event_data: dict, prev_hash: str | None = None) -> str:
    """
    Генерация хеша для аудит-лога (цепочка)
    """
    data_str = str(event_data) + (prev_hash or "")
    return hashlib.sha256(data_str.encode()).hexdigest()


def generate_device_fingerprint(user_agent: str, ip: str) -> str:
    """
    Генерация отпечатка устройства
    """
    fingerprint_data = f"{user_agent}:{ip}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()


if __name__ == "__main__":
    # Тестирование
    print("=== ТЕСТ AUTH UTILS ===")
    
    # 1. Хеширование пароля
    password = "admin123"
    hashed = hash_password(password)
    print(f"\nПароль: {password}")
    print(f"Хеш: {hashed[:50]}...")
    print(f"Верификация: {verify_password(password, hashed)}")
    
    # 2. JWT токены
    user_data = {"user_id": 1, "role": "ADMIN"}
    access_token = create_access_token(user_data)
    print(f"\nAccess Token: {access_token[:50]}...")
    decoded = decode_token(access_token)
    print(f"Decoded: {decoded}")
    
    # 3. MFA секрет
    mfa_secret = generate_mfa_secret()
    totp_uri = generate_totp_uri(mfa_secret, "admin@elections.kz")
    print(f"\nMFA Secret: {mfa_secret}")
    print(f"TOTP URI: {totp_uri}")
    
    # 4. QR токен для чек-ина
    qr_token = generate_qr_token(precinct_id=1, observer_id=1)
    print(f"\nQR Token: {qr_token[:50]}...")
    
    # 5. Хеш файла
    test_file = b"test file content"
    file_hash = hash_file(test_file)
    print(f"\nFile Hash: {file_hash}")
    
    # 6. Аудит-цепочка
    event1 = {"action": "login", "user_id": 1}
    hash1 = generate_audit_hash(event1)
    event2 = {"action": "upload_protocol", "user_id": 1}
    hash2 = generate_audit_hash(event2, hash1)
    print(f"\nAudit Chain:")
    print(f"  Event 1 Hash: {hash1}")
    print(f"  Event 2 Hash: {hash2}")
