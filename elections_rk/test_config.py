import os
from pathlib import Path

# Показать текущую директорию
print(f"Current directory: {os.getcwd()}")

# Проверить существование .env
env_path = Path(".env")
print(f".env exists: {env_path.exists()}")
if env_path.exists():
    print(f".env full path: {env_path.absolute()}")
    print(f".env contents:\n{env_path.read_text()}")

# Попробовать загрузить конфиг
try:
    from app.config import settings
    print(f"\nSettings loaded successfully!")
    print(f"database_url from settings: {settings.database_url}")
except Exception as e:
    print(f"\nError loading settings: {e}")
    import traceback
    traceback.print_exc()
