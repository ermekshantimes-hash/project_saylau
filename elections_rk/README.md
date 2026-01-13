# Система открытого голосования РК (RK Elections Open Results)

## ✅ Статус проекта: ЗАПУЩЕН И РАБОТАЕТ

### 🚀 Быстрый старт

1. **Запустите сервер** (если ещё не запущен):
   ```
   C:\elections_rk\run_server.bat
   ```

2. **Откройте интерфейсы:**
   - 📊 **Аналитика с графиками**: C:\elections_rk\frontend\analytics.html
   - 🗺️ **Интерактивная карта РК**: C:\elections_rk\frontend\map.html
   - 🏠 **Главная страница**: C:\elections_rk\frontend\index.html
   - 📤 **Загрузка протоколов**: C:\elections_rk\frontend\upload.html
   - 📍 **Детали участка**: C:\elections_rk\frontend\precinct.html
   - 🔧 **API документация (Swagger)**: http://127.0.0.1:8888/docs

3. **Запустите Telegram бота** (опционально):
   ```
   # Сначала получите токен у @BotFather в Telegram
   # Добавьте в .env: TELEGRAM_BOT_TOKEN=ваш_токен
   C:\elections_rk\start_bot.bat
   ```

### 📁 Структура проекта

```
C:\elections_rk\
├── app\                      # Backend FastAPI
│   ├── main.py              # Основное приложение + Analytics API
│   ├── models.py            # SQLAlchemy модели
│   ├── config.py            # Конфигурация (pydantic-settings)
│   └── database.py          # Подключение к БД
├── database\
│   ├── init.sql             # Схема БД (7 таблиц)
│   └── seed_data.sql        # Тестовые данные
├── frontend\
│   ├── analytics.html       # 📊 Аналитика, графики, диаграммы
│   ├── map.html             # 🗺️ Интерактивная карта РК
│   ├── index.html           # 🏠 Главная страница
│   ├── precinct.html        # 📍 Детали участка
│   └── upload.html          # 📤 Загрузка протоколов
├── telegram_bot.py          # 🤖 Telegram бот
├── .env                     # Конфигурация (DATABASE_URL, BOT_TOKEN)
├── run_server.bat           # Запуск FastAPI сервера
└── start_bot.bat            # Запуск Telegram бота

```

### 🗄️ База данных

- **СУБД:** PostgreSQL 18.1
- **Название БД:** elections_rk
- **Порт:** 5432
- **Пользователь:** postgres
- **Пароль:** 23june1970

**Таблицы:**
- elections - выборы (2 записи: Президентские 2024, Мажилис 2024)
- 
egions - иерархия регионов (20 областей РК)
- precincts - избирательные участки (4 тестовых)
- election_subjects - кандидаты/партии (11 кандидатов)
- precinct_results - результаты по участкам
- protocol_photos - фото протоколов от наблюдателей
- 
egion_summary_results - агрегированные результаты

### 🔌 API Endpoints

**Основные:**
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Информация об API |
| GET | `/api/elections` | Список всех выборов |
| GET | `/api/elections/{id}` | Детали выборов |
| GET | `/api/elections/{id}/regions` | Регионы верхнего уровня |
| GET | `/api/elections/{id}/subjects` | Кандидаты/партии |
| GET | `/api/regions/{id}/children` | Подрегионы |
| GET | `/api/regions/{id}/precincts` | Участки региона |
| GET | `/api/precincts/{pid}/results/{eid}` | Результаты участка |
| POST | `/api/protocol/upload` | Загрузка фото протокола |

**🆕 Аналитика:**
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/analytics/elections/{id}/summary` | Общая статистика по выборам |
| GET | `/api/analytics/elections/{id}/by_region` | Результаты по регионам |
| GET | `/api/analytics/elections/{id}/comparison` | Сравнительная таблица кандидатов |
| GET | `/api/analytics/elections/{id}/charts` | Данные для графиков (pie, bar) |

### 🛠️ Технологии

**Backend:**
- FastAPI 0.115+
- SQLAlchemy 2.0+
- PostgreSQL (psycopg2-binary)
- Python 3.11.9
- Pydantic 2.x (settings)
- Uvicorn (ASGI сервер)
- python-telegram-bot (async bot)
- aiohttp (async HTTP клиент)

**Frontend:**
- Vanilla JavaScript
- HTML5 + CSS3
- Fetch API для HTTP запросов
- Leaflet.js 1.9.4 (карты)
- Chart.js 4.4.0 (графики)

### 🤖 Telegram Bot

Бот для мониторинга выборов в реальном времени через Telegram.

**Команды:**
- `/start` - Приветствие и информация о боте
- `/elections` - Список активных выборов с кнопками
- `/results` - Результаты выбранных выборов
- `/regions` - Результаты по регионам
- `/analytics` - Аналитика и статистика
- `/help` - Справка по командам

**Запуск:**
```bash
# 1. Получите токен от @BotFather в Telegram
# 2. Добавьте TELEGRAM_BOT_TOKEN в .env файл
# 3. Запустите бота
start_bot.bat
```

**Настройка:**
1. Откройте Telegram, найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot` и следуйте инструкциям
3. Скопируйте полученный токен
4. Добавьте в файл `.env`:
   ```
   TELEGRAM_BOT_TOKEN=ваш_токен_здесь
   ```

### 📊 Данные для тестирования

**Выборы:**
1. ID=1: Президентские выборы 2024 (20.11.2024)
2. ID=2: Выборы в Мажилис 2024 (19.03.2024)

**Регионы (примеры):**
- ID=1: Акмолинская область (код: AKMO)
- ID=2: Актюбинская область (код: AKTU)
- ID=3: Алматинская область (код: ALMI)
- ID=4: Атырауская область (код: ATYR)

**Участки (примеры):**
- ID=1: Участок №101 (Акмолинская обл.)
- ID=2: Участок №102 (Актюбинская обл.)
- ID=3: Участок №103 (Алматинская обл.)
- ID=4: Участок №201 (Атырауская обл.)

### 🔧 Устранение неполадок

**Сервер не запускается:**
1. Убедитесь, что PostgreSQL запущен:
   ``powershell
   Get-Service postgresql-x64-18
   ``

2. Проверьте соединение с БД:
   ``powershell
   ='23june1970'; & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d elections_rk -c "SELECT version();"
   ``

3. Проверьте, что порт 8000 свободен:
   ``powershell
   netstat -ano | Select-String "8000"
   ``

**Кириллица не отображается:**
- В браузере кириллица должна отображаться корректно
- В PowerShell консоли могут быть кракозябры (это нормально для вывода JSON с UTF-8)

**Ошибка password authentication failed:**
- Убедитесь, что файл .env без BOM (проверьте первую строку - не должно быть п»ї)
- Пересоздайте .env:
  ``powershell
  Remove-Item .env; [System.IO.File]::WriteAllLines("C:\elections_rk\.env", @("DATABASE_URL=postgresql://postgres:23june1970@localhost:5432/elections_rk"), (New-Object System.Text.UTF8Encoding False))
  ``

### 📝 Примеры использования API

**Получить список выборов:**
``bash
curl http://127.0.0.1:8888/api/elections
``

**Получить регионы:**
``bash
curl http://127.0.0.1:8888/api/elections/1/regions
``

**Получить результаты участка:**
``bash
curl http://127.0.0.1:8888/api/precincts/1/results/1
``

**Загрузить протокол:**
``bash
curl -X POST http://127.0.0.1:8888/api/protocol/upload \
  -F "election_id=1" \
  -F "precinct_id=1" \
  -F "observer_name=Иван Петров" \
  -F "[email protected]"
``

### 🎯 Возможности системы

✅ **Реализовано:**
- Иерархическая структура регионов (5 уровней)
- Хранение результатов по участкам
- API для получения данных в реальном времени
- Загрузка фотографий протоколов
- CORS для работы с frontend
- Swagger документация

🚧 **Для продакшена (требуется доработка):**
- Авторизация и аутентификация
- Валидация загружаемых протоколов (OCR)
- Кеширование результатов (Redis)
- WebSocket для real-time обновлений
- Полные данные всех 12,000 участков РК
- Деплой (Docker, Kubernetes)
- Мониторинг (Prometheus, Grafana)
- Резервное копирование БД

### 👥 Контакты

Проект создан с помощью GitHub Copilot
Дата: 1 декабря 2025
#   p r o j e c t _ s a y l a u  
 