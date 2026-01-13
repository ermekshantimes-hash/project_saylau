# Руководство по установке и запуску Elections RK

## Проблема с текущей конфигурацией

**Обнаружена проблема:** Python 3.12.11 в `venv` (созданном через msys64) не поддерживает компиляцию пакетов `pydantic-core` и `watchfiles`, требующих Rust toolchain.

## Решения (варианты)

### Вариант 1: Использовать Python 3.11 (рекомендуется)

1. Удалите текущий `venv`:
```powershell
Remove-Item -Recurse -Force .\venv
```

2. Установите Python 3.11 с [python.org/downloads](https://www.python.org/downloads/) (выберите версию 3.11.x для Windows).

3. Создайте новый venv с Python 3.11:
```powershell
py -3.11 -m venv venv
```

4. Активируйте и установите зависимости:
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install aiohttp python-telegram-bot python-dotenv
```

5. Запустите сервер и бота:
```powershell
# Терминал 1 - FastAPI сервер
.\start_server.bat

# Терминал 2 - Telegram бот
.\start_bot.bat
```

### Вариант 2: Использовать Docker (проще всего)

1. Установите [Docker Desktop](https://www.docker.com/products/docker-desktop/)

2. Создайте `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install aiohttp python-telegram-bot python-dotenv

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. Запустите через Docker Compose или вручную:
```powershell
docker build -t elections-rk .
docker run -p 8000:8000 --env-file .env elections-rk
```

### Вариант 3: Установить Rust toolchain (для опытных пользователей)

1. Установите Rust с [rustup.rs](https://rustup.rs/)

2. После установки перезапустите PowerShell и попробуйте установить зависимости снова:
```powershell
.\venv\bin\python.exe -m pip install -r requirements.txt
```

### Вариант 4: Использовать WSL2 (Windows Subsystem for Linux)

1. Установите WSL2 и Ubuntu:
```powershell
wsl --install
```

2. В Ubuntu терминале:
```bash
cd /mnt/c/elections_rk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install aiohttp python-telegram-bot python-dotenv
```

3. Запустите сервер и бота из WSL:
```bash
# Терминал 1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Терминал 2
python telegram_bot.py
```

## Текущий статус бота

✅ **Telegram бот настроен и готов к работе**
- Новый токен установлен в `.env`
- Бот запускается командой: `.\venv\bin\python.exe .\telegram_bot.py`
- Username бота: `@SaylauMonitor_bot`

⚠️ **FastAPI сервер требует исправления окружения**
- Текущий `venv` не поддерживает компиляцию Rust-зависимостей
- Выберите один из вариантов выше для запуска сервера

## Быстрый старт (после решения проблемы с venv)

1. **Запустите PostgreSQL базу данных:**
```powershell
.\init_database.bat
```

2. **Запустите FastAPI сервер:**
```powershell
.\start_server.bat
```
Сервер будет доступен по адресу: http://localhost:8000

3. **Запустите Telegram бота:**
```powershell
.\start_bot.bat
```

4. **Откройте бота в Telegram:**
   - Найдите `@SaylauMonitor_bot`
   - Отправьте `/start`

## Полезные команды

```powershell
# Проверить токен бота
Get-Content .\.env | Select-String "TELEGRAM_BOT_TOKEN"

# Проверить версию Python
python --version

# Проверить установленные пакеты
pip list

# Остановить все процессы Python
taskkill /F /IM python.exe

# Проверить порты (8000 для API)
netstat -an | Select-String ":8000"
```

## Troubleshooting

### Бот не отвечает
1. Проверьте, что токен правильно установлен в `.env`
2. Убедитесь, что нет конфликтующих процессов: `taskkill /F /IM python.exe`
3. Перезапустите бота

### API не доступен
1. Проверьте, что PostgreSQL запущен
2. Убедитесь, что порт 8000 не занят
3. Проверьте логи сервера

### Ошибки импорта модулей
1. Убедитесь, что используете правильный интерпретатор из venv
2. Переустановите зависимости: `pip install -r requirements.txt`

## Дополнительная информация

- API документация: http://localhost:8000/docs
- Интерактивная документация: http://localhost:8000/redoc
- Фронтенд: `file:///C:/elections_rk/frontend/index.html`

## Безопасность

⚠️ **ВАЖНО:**
- Никогда не публикуйте `.env` файл
- Храните токен бота в секрете
- Для продакшена используйте переменные окружения
- Отзовите старый токен через @BotFather: `/revoke`
