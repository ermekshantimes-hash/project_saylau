# 📖 Инструкция по запуску системы Elections RK

## ✅ Предварительные проверки

### 1. Проверка PostgreSQL
```powershell
# Проверить службу
Get-Service -Name "*postgres*"

# Должно показать: Status = Running
```

### 2. Проверка виртуального окружения
```powershell
# Активировать venv
.\venv\Scripts\Activate.ps1

# Проверить Python
python --version
# Должно показать: Python 3.11.9

# Проверить установленные пакеты
pip list | Select-String "fastapi|uvicorn|sqlalchemy"
```

---

## 🗄️ Инициализация базы данных

### Вариант А: Первый запуск (база пустая)

```powershell
# 1. Создать базу данных
psql -U postgres -c "DROP DATABASE IF EXISTS elections_db;"
psql -U postgres -c "CREATE DATABASE elections_db ENCODING 'UTF8';"

# 2. Создать схему (таблицы)
psql -U postgres -d elections_db -f database\init_utf8.sql

# 3. Добавить 12,000 УИК
psql -U postgres -d elections_db -f database\expand_12k_precincts.sql

# 4. Добавить тестовые данные
psql -U postgres -d elections_db -f database\seed_observers_test.sql

# 5. Проверить данные
psql -U postgres -d elections_db -c "SELECT COUNT(*) FROM precincts;"
# Должно показать: 12000

psql -U postgres -d elections_db -c "SELECT COUNT(*) FROM observer_profiles;"
# Должно показать: ~1000
```

### Вариант Б: База уже существует (обновление)

```powershell
# Просто запустить сервер — таблицы создадутся автоматически
# (благодаря Base.metadata.create_all() в main.py)
```

---

## 🚀 Запуск сервера

### Способ 1: Через батник (рекомендуется для разработки)

```powershell
# Запуск с автоперезагрузкой при изменении кода
.\start_server.bat
```

Или вручную:
```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8001 --reload
```

### Способ 2: Production режим (без reload)

```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Проверка запуска

Откройте в браузере:
```
http://127.0.0.1:8001/docs
```

Должна открыться **Swagger UI** с документацией API.

---

## 🧪 Тестирование API

### 1. Проверка health endpoint'ов

```powershell
# Public API health
curl http://127.0.0.1:8001/public/health

# Media service health
curl http://127.0.0.1:8001/media/health

# Crisis management status
curl http://127.0.0.1:8001/crisis/status
```

### 2. Получение публичных данных (без авторизации)

```powershell
# Список выборов
curl http://127.0.0.1:8001/public/elections

# Регионы
curl http://127.0.0.1:8001/public/regions

# УИК (первые 10)
curl "http://127.0.0.1:8001/public/precincts?limit=10"

# Статистика наблюдателей
curl http://127.0.0.1:8001/public/stats/observers

# Статистика протоколов
curl http://127.0.0.1:8001/public/stats/protocols
```

### 3. Регистрация и авторизация

```powershell
# Регистрация нового наблюдателя
curl -X POST http://127.0.0.1:8001/auth/register-observer `
  -H "Content-Type: application/json" `
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "full_name": "Тестовый Наблюдатель"
  }'

# Логин (получение токена)
$response = curl -X POST http://127.0.0.1:8001/auth/login `
  -H "Content-Type: application/json" `
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }' | ConvertFrom-Json

$token = $response.access_token
Write-Host "Token: $token"

# Использование токена для защищённых запросов
curl http://127.0.0.1:8001/auth/me `
  -H "Authorization: Bearer $token"
```

### 4. Запуск автоматических тестов

```powershell
# Тесты public API
.\venv\Scripts\python.exe test_public_fastapi.py

# Тесты crisis management
.\venv\Scripts\python.exe test_crisis_api.py

# Тесты fraud detection (если есть)
.\venv\Scripts\python.exe -m pytest tests/test_fraud.py -v
```

---

## 🌐 Открытие веб-интерфейса

### 1. Главная страница результатов
```
http://127.0.0.1:8001/static/index.html
```
Или откройте файл напрямую:
```powershell
start frontend\index.html
```

### 2. Режим реального времени (WebSocket)
```
http://127.0.0.1:8001/static/realtime.html
```
Или:
```powershell
start frontend\realtime.html
```

### 3. Другие страницы
```powershell
start frontend\analytics.html   # Аналитика
start frontend\map.html         # Карта
start frontend\precinct.html    # Детали УИК
start frontend\upload.html      # Загрузка протоколов
```

---

## 🔧 Полезные команды

### Просмотр логов сервера

Uvicorn выводит логи в консоль. Для сохранения в файл:
```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8001 --reload 2>&1 | Tee-Object -FilePath "server.log"
```

### Остановка сервера

Нажмите **Ctrl+C** в окне терминала или:
```powershell
# Найти процесс
Get-Process -Name "uvicorn" | Select-Object Id, ProcessName

# Завершить процесс
Stop-Process -Name "uvicorn" -Force
```

### Проверка открытых портов

```powershell
# Проверить, занят ли порт 8001
Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue

# Если занят — найти процесс
Get-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess
```

### Очистка кэша Python

```powershell
# Удалить __pycache__
Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force

# Удалить .pyc файлы
Get-ChildItem -Path . -Filter "*.pyc" -Recurse | Remove-Item -Force
```

---

## 📊 Типичные сценарии использования

### Сценарий 1: Наблюдатель загружает протокол

1. Зарегистрироваться через `/auth/register-observer`
2. Войти через `/auth/login` → получить токен
3. Создать профиль через `/observers/my-profile`
4. Подать заявку на УИК через `/observers/applications`
5. Координатор одобряет через `/observers/applications/{id}/assign`
6. Check-in на УИК через `/observers/checkin`
7. Загрузить протокол через `/protocols/upload`
8. Добавить результаты через `/protocols/{id}/items`

### Сценарий 2: Координатор проверяет протоколы

1. Войти как COORD/ADMIN
2. Посмотреть список протоколов: `/protocols?status=UNDER_REVIEW`
3. Скачать фото протокола: `/media/download/{bucket}/{object_name}`
4. Проверить результаты: `/protocols/{id}`
5. Подтвердить: `/protocols/{id}/verify` (status=VERIFIED)

### Сценарий 3: Анализ мошенничества

1. Войти как ADMIN
2. Запустить полное сканирование: `/fraud/full-scan`
3. Посмотреть дубликаты наблюдателей: `/fraud/duplicates/observers`
4. Посмотреть аномалии явки: `/fraud/anomalies/turnout`
5. Получить risk score наблюдателя: `/fraud/observer-risk/{id}`
6. Посмотреть критические алерты: `/fraud/critical-alerts`

### Сценарий 4: Кризисное управление

1. Включить read-only режим: `POST /crisis/read-only/enable`
2. Проверить статус: `GET /crisis/status`
3. Получить failover URLs: `GET /crisis/failover-urls`
4. Создать snapshot: `POST /crisis/emergency-snapshot`
5. Выключить read-only: `POST /crisis/read-only/disable`

---

## 🔑 Тестовые учетные записи

После выполнения `seed_observers_test.sql`:

```
Email: admin@elections.kz
Password: Admin123!
Role: ADMIN

Email: coordinator@elections.kz
Password: Coord123!
Role: COORD

Email: observer1@example.com
Password: Observer123!
Role: OBSERVER
```

---

## ⚠️ Решение проблем

### Ошибка: "Address already in use"
```powershell
# Порт 8001 занят — найти и завершить процесс
$process = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $process.OwningProcess -Force
}
```

### Ошибка: "FATAL: password authentication failed"
```powershell
# Проверить пароль PostgreSQL в app/config.py
# По умолчанию: postgres / 101112
```

### Ошибка: "No module named 'app'"
```powershell
# Убедиться, что venv активирован
.\venv\Scripts\Activate.ps1

# Запускать из корня проекта (C:\elections_rk)
cd C:\elections_rk
```

### Ошибка: "relation does not exist"
```powershell
# База данных пустая — создать схему
psql -U postgres -d elections_db -f database\init_utf8.sql
```

---

## 📞 API Endpoints (краткий справочник)

### Public (без авторизации)
- `GET /public/elections` - Список выборов
- `GET /public/regions` - Регионы
- `GET /public/precincts` - УИК
- `GET /public/stats/observers` - Статистика наблюдателей
- `GET /public/health` - Health check

### Auth
- `POST /auth/register-observer` - Регистрация
- `POST /auth/login` - Вход
- `POST /auth/refresh` - Обновление токена
- `GET /auth/me` - Профиль пользователя

### Observers (требуется токен)
- `GET /observers/my-profile` - Мой профиль
- `POST /observers/my-profile` - Создать профиль
- `POST /observers/applications` - Подать заявку на УИК
- `POST /observers/checkin` - Check-in на УИК

### Protocols (требуется токен)
- `POST /protocols/upload` - Загрузить протокол
- `POST /protocols/{id}/items` - Добавить результаты
- `GET /protocols` - Список протоколов
- `POST /protocols/{id}/verify` - Проверить протокол

### Fraud Detection (ADMIN/COORD)
- `GET /fraud/full-scan` - Полное сканирование
- `GET /fraud/duplicates/observers` - Дубликаты наблюдателей
- `GET /fraud/anomalies/turnout` - Аномалии явки
- `GET /fraud/observer-risk/{id}` - Risk score наблюдателя

### Crisis Management (ADMIN)
- `POST /crisis/read-only/enable` - Включить read-only
- `POST /crisis/maintenance/enable` - Включить maintenance
- `GET /crisis/status` - Статус системы
- `GET /crisis/health` - Health check

---

## 🎯 Быстрый старт (TL;DR)

```powershell
# 1. Инициализация БД (только первый раз)
.\init_database.bat

# 2. Запуск сервера
.\start_server.bat

# 3. Открыть в браузере
start http://127.0.0.1:8001/docs

# 4. Открыть фронтенд
start frontend\index.html
```

**Готово!** 🚀

---

## 📚 Дополнительные ресурсы

- Swagger UI: http://127.0.0.1:8001/docs
- ReDoc: http://127.0.0.1:8001/redoc
- OpenAPI JSON: http://127.0.0.1:8001/openapi.json
- Отчёт о проверке кода: `CODE_REVIEW_REPORT.md`
- Быстрый старт: `QUICKSTART.md`
