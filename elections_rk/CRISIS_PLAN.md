# Crisis Management Plan (Task #16)

## 🚨 Обзор

Система управления кризисными ситуациями для платформы выборов РК с поддержкой:
- **Read-only режим** - блокировка записи при высокой нагрузке
- **Maintenance режим** - техническое обслуживание
- **CDN Fallback** - переключение на статические зеркала
- **Strict Rate Limits** - ужесточение лимитов запросов

---

## 📁 Файлы

### Основные модули
- `app/crisis_mode.py` - управление состоянием кризиса
- `app/routes_crisis.py` - API endpoints для управления
- `data/crisis_state.json` - persistent хранилище состояния

---

## 🔧 API Endpoints

### Публичные (без авторизации)

#### `GET /api/crisis/status`
Текущий статус системы

**Response:**
```json
{
  "read_only": false,
  "maintenance": false,
  "cdn_fallback": false,
  "rate_limit_strict": false,
  "reason": null,
  "activated_at": null,
  "activated_by": null
}
```

#### `GET /api/crisis/health`
Проверка здоровья системы

**Response:**
```json
{
  "status": "operational",
  "read_only": false,
  "maintenance": false,
  "timestamp": "2024-11-20T10:00:00",
  "database_ok": true,
  "api_responsive": true
}
```

#### `GET /api/crisis/failover-urls`
Список резервных URL

**Response:**
```json
{
  "primary": "https://elections.gov.kz",
  "mirrors": [
    "https://elections-mirror1.gov.kz",
    "https://elections-mirror2.gov.kz",
    "https://elections-mirror3.gov.kz"
  ],
  "cdn": [
    "https://cdn1.elections.gov.kz",
    "https://cdn2.elections.gov.kz"
  ],
  "status_page": "https://status.elections.gov.kz"
}
```

---

### Административные (ADMIN only)

#### `POST /api/crisis/read-only/enable`
Включить read-only режим

**Request:**
```json
{
  "reason": "Высокая нагрузка на БД"
}
```

#### `POST /api/crisis/read-only/disable`
Выключить read-only режим

#### `POST /api/crisis/maintenance/enable`
Включить maintenance режим

**Request:**
```json
{
  "reason": "Плановое обновление ПО"
}
```

#### `POST /api/crisis/maintenance/disable`
Выключить maintenance режим

#### `POST /api/crisis/cdn/enable`
Переключить на CDN fallback

#### `POST /api/crisis/cdn/disable`
Отключить CDN fallback

#### `POST /api/crisis/rate-limits/strict`
Ужесточить rate limits (снизить на 50%)

#### `POST /api/crisis/rate-limits/normal`
Вернуть нормальные rate limits

#### `POST /api/crisis/emergency-snapshot`
Создать аварийный snapshot данных

**Response:**
```json
{
  "success": true,
  "file": "data/snapshots/emergency_20241120_100000.json",
  "size_bytes": 1048576,
  "total_votes": 5000000
}
```

---

## 🎯 Сценарии использования

### Сценарий 1: Высокая нагрузка в день выборов

**Проблема:** База данных перегружена запросами на запись

**Решение:**
1. Включить read-only режим:
   ```bash
   POST /api/crisis/read-only/enable
   {"reason": "Пиковая нагрузка - день выборов"}
   ```

2. Включить strict rate limits:
   ```bash
   POST /api/crisis/rate-limits/strict
   ```

3. Мониторить нагрузку через `/api/crisis/health`

4. После снижения нагрузки отключить ограничения:
   ```bash
   POST /api/crisis/read-only/disable
   POST /api/crisis/rate-limits/normal
   ```

---

### Сценарий 2: DDoS атака

**Проблема:** Массовые запросы от ботов

**Решение:**
1. Включить strict rate limits немедленно
2. Переключить на CDN для статического контента:
   ```bash
   POST /api/crisis/cdn/enable
   ```
3. Создать emergency snapshot для CDN:
   ```bash
   POST /api/crisis/emergency-snapshot
   ```
4. Распространить snapshot на CDN зеркала
5. Настроить Web Application Firewall (WAF)

---

### Сценарий 3: Критическая ошибка БД

**Проблема:** База данных недоступна

**Решение:**
1. Включить maintenance режим:
   ```bash
   POST /api/crisis/maintenance/enable
   {"reason": "Критическая ошибка БД - восстановление"}
   ```

2. Включить CDN fallback для публичных данных
3. Восстановить БД из backup
4. Протестировать систему
5. Отключить maintenance:
   ```bash
   POST /api/crisis/maintenance/disable
   ```

---

### Сценарий 4: Плановое обслуживание

**Проблема:** Нужно обновить ПО ночью

**Решение:**
1. За 1 час до обслуживания - уведомить пользователей
2. Включить maintenance режим в назначенное время
3. Выполнить обновления
4. Запустить тесты
5. Отключить maintenance режим
6. Мониторить систему 30 минут

---

## 🔄 CDN Failover Architecture

### Архитектура

```
                    ┌─────────────┐
                    │   DNS LB    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼───┐   ┌───▼────┐  ┌───▼────┐
         │Primary │   │Mirror 1│  │Mirror 2│
         │ Server │   │        │  │        │
         └────┬───┘   └───┬────┘  └───┬────┘
              │           │            │
         ┌────▼───────────▼────────────▼────┐
         │         PostgreSQL DB            │
         │      (Replication cluster)       │
         └─────────────────────────────────┘
                      │
              ┌───────┴────────┐
              │                │
         ┌────▼────┐      ┌───▼────┐
         │  CDN 1  │      │  CDN 2 │
         │(Static) │      │(Static)│
         └─────────┘      └────────┘
```

### Компоненты

1. **Primary Server** - основной FastAPI сервер
2. **Mirror Servers** - резервные копии (read-only)
3. **PostgreSQL Cluster** - реплицированная БД
4. **CDN Layer** - кэш для статических данных и результатов

---

## 📊 Мониторинг

### Метрики для отслеживания

1. **CPU Usage** - > 80% → включить read-only
2. **Database Connections** - > 90% → включить read-only
3. **Response Time** - > 2s → включить strict limits
4. **Error Rate** - > 5% → включить maintenance
5. **Request Rate** - > 10K/min → включить strict limits

### Prometheus Metrics (для будущей интеграции)

```python
# Примеры метрик
crisis_mode_active{mode="read_only"} 0|1
crisis_mode_active{mode="maintenance"} 0|1
crisis_mode_active{mode="cdn_fallback"} 0|1
http_requests_total{status="503"} counter
database_connections_active gauge
```

---

## 🛠️ Тестирование

### Тест 1: Read-only режим

```bash
# Включить
curl -X POST http://localhost:8001/api/crisis/read-only/enable \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test"}'

# Попытка записи (должна вернуть 503)
curl -X POST http://localhost:8001/api/protocols/upload

# Отключить
curl -X POST http://localhost:8001/api/crisis/read-only/disable \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Тест 2: Maintenance режим

```bash
# Включить
curl -X POST http://localhost:8001/api/crisis/maintenance/enable \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"reason": "Test maintenance"}'

# Любой запрос (кроме health) должен вернуть 503
curl http://localhost:8001/api/elections

# Health endpoint должен работать
curl http://localhost:8001/api/crisis/health

# Отключить
curl -X POST http://localhost:8001/api/crisis/maintenance/disable \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 📝 Чек-лист для кризисных ситуаций

### Перед выборами (за 1 неделю)

- [ ] Протестировать все crisis endpoints
- [ ] Создать fresh snapshot данных
- [ ] Проверить доступность всех mirror URLs
- [ ] Настроить CDN кэширование
- [ ] Провести load testing
- [ ] Подготовить runbooks для операторов
- [ ] Настроить alerting в Telegram/Email

### В день выборов

- [ ] Дежурная команда на связи 24/7
- [ ] Мониторинг метрик каждые 5 минут
- [ ] Готовность включить read-only за 30 секунд
- [ ] Snapshots каждый час
- [ ] Backup логов

### После выборов

- [ ] Анализ инцидентов
- [ ] Review всех включений crisis режимов
- [ ] Обновление runbooks
- [ ] Оптимизация узких мест

---

## 🚀 Deployment

### Production Setup

1. **Настроить переменные окружения:**
   ```bash
   CRISIS_STATE_FILE=/var/data/crisis_state.json
   CDN_MIRRORS=https://cdn1.elections.gov.kz,https://cdn2.elections.gov.kz
   EMERGENCY_CONTACT=ops@elections.gov.kz
   ```

2. **Настроить Nginx для failover:**
   ```nginx
   upstream backend {
       server primary.elections.gov.kz:8001 max_fails=3 fail_timeout=30s;
       server mirror1.elections.gov.kz:8001 backup;
       server mirror2.elections.gov.kz:8001 backup;
   }
   
   server {
       location / {
           proxy_pass http://backend;
           proxy_next_upstream error timeout http_503;
       }
   }
   ```

3. **Настроить PostgreSQL Streaming Replication**

4. **Настроить CDN (CloudFlare/Akamai)**

---

## 📞 Контакты дежурной команды

- **Техническая поддержка:** ops@elections.gov.kz
- **Дежурный администратор:** +7-XXX-XXX-XXXX
- **Telegram канал:** @elections_ops
- **Status Page:** https://status.elections.gov.kz

---

## ✅ Итоги Task #16

**Реализовано:**
- ✅ Crisis mode management модуль
- ✅ API endpoints для управления (10 endpoints)
- ✅ Read-only режим с middleware
- ✅ Maintenance режим
- ✅ CDN fallback support
- ✅ Emergency snapshot создание
- ✅ Failover URLs
- ✅ Health check endpoint
- ✅ Persistent state storage
- ✅ Документация и runbooks

**Готово к production!** 🎉
