# Audit API Quick Reference

## Authentication
All audit endpoints require authentication with ADMIN or COORD role (except where specified).

```bash
# Get access token first
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "+77000000000", "password": "your_password"}'

# Use token in requests
export TOKEN="your_access_token_here"
```

---

## Endpoints

### 1. Get Audit Events (ADMIN + COORD)
```bash
GET /api/audit/events

# With filters
GET /api/audit/events?scope=USER&event_type=LOGIN&skip=0&limit=100

# Query parameters:
# - skip: int (default 0)
# - limit: int (default 100, max 500)
# - scope: str (USER, SYSTEM, DATA_ENTRY)
# - event_type: str (LOGIN, PROTOCOL_UPLOADED, etc.)
# - actor_user_id: int
# - start_date: datetime (ISO format)
# - end_date: datetime (ISO format)
```

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/api/audit/events?limit=10"
```

**Response**:
```json
[
  {
    "id": 1,
    "actor_user_id": 1,
    "actor_name": "Admin User",
    "scope": "SYSTEM",
    "event_type": "SYSTEM_INIT",
    "payload_json": {"message": "Audit log initialized"},
    "ts": "2025-01-26T10:30:00",
    "hash": "3285689e153da5c3...",
    "prev_hash": null
  }
]
```

---

### 2. Get Single Event (ADMIN + COORD)
```bash
GET /api/audit/events/{event_id}
```

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/audit/events/1
```

---

### 3. Get Audit Statistics (ADMIN only)
```bash
GET /api/audit/stats
```

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/audit/stats
```

**Response**:
```json
{
  "total_events": 156,
  "events_last_24h": 42,
  "events_last_7d": 98,
  "events_by_scope": {
    "USER": 120,
    "SYSTEM": 30,
    "DATA_ENTRY": 6
  },
  "events_by_type_top10": [
    {"event_type": "LOGIN", "count": 45},
    {"event_type": "PROTOCOL_UPLOADED", "count": 32}
  ],
  "first_event_ts": "2025-01-26T10:00:00",
  "last_event_ts": "2025-01-26T18:30:00"
}
```

---

### 4. Verify Hash Chain (ADMIN only)
```bash
POST /api/audit/verify-chain?start_id=1&end_id=100
```

**Example**:
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/api/audit/verify-chain"
```

**Response (valid chain)**:
```json
{
  "status": "valid",
  "message": "Audit chain is valid",
  "total_events": 156,
  "first_event_id": 1,
  "last_event_id": 156,
  "broken_events": null
}
```

**Response (broken chain)**:
```json
{
  "status": "broken",
  "message": "Found 2 broken events",
  "total_events": 156,
  "broken_events": [
    {
      "id": 45,
      "expected_prev_hash": "abc123...",
      "actual_prev_hash": "def456..."
    }
  ]
}
```

---

### 5. Get User History (ADMIN + COORD)
```bash
GET /api/audit/user/{user_id}/history?skip=0&limit=50
```

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/audit/user/1/history
```

---

### 6. Get Precinct History (ADMIN + COORD)
```bash
GET /api/audit/precinct/{precinct_id}/history?skip=0&limit=50
```

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/audit/precinct/100/history
```

---

### 7. Export Audit Log (ADMIN only)
```bash
GET /api/audit/export?start_date=2025-01-01&end_date=2025-01-31
```

**Limits**: Maximum 10,000 records

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/api/audit/export?start_date=2025-01-26T00:00:00" \
  > audit_export.json
```

---

## Event Types

Common event types logged by the system:

| Event Type | Description |
|------------|-------------|
| `USER_LOGIN` | User authentication |
| `USER_LOGOUT` | User logout |
| `PROFILE_VERIFIED` | Observer profile verification |
| `PROTOCOL_UPLOADED` | Protocol file uploaded |
| `PROTOCOL_VERIFIED` | Protocol verification by coordinator |
| `TALLY_CREATED` | Vote tally created/updated |
| `INCIDENT_CREATED` | Incident reported |
| `INCIDENT_RESOLVED` | Incident resolution |
| `SYSTEM_INIT` | System initialization |
| `DB_MIGRATION` | Database migration applied |
| `AUDIT_CHAIN_VERIFY` | Chain verification performed |
| `AUDIT_LOG_EXPORT` | Logs exported by admin |

---

## Scope Types

| Scope | Description |
|-------|-------------|
| `USER` | User-initiated actions (login, uploads, etc.) |
| `SYSTEM` | System-generated events (migrations, cron jobs) |
| `DATA_ENTRY` | Data entry operations (manual data corrections) |

---

## Manual Logging

Use the helper functions in `app/audit.py`:

```python
from app.audit import (
    log_user_login,
    log_profile_verification,
    log_protocol_upload,
    log_protocol_verification,
    log_tally_created,
    log_incident_created,
    log_system_event
)

# Example: Log user login
log_user_login(
    user_id=1,
    ip="192.168.1.100",
    db=db
)

# Example: Log system event
log_system_event(
    event_type="BACKUP_COMPLETED",
    payload={"backup_size_mb": 1024, "duration_sec": 45},
    db=db
)
```

---

## Hash Chain Verification

The audit system uses SHA256 hash chains to ensure integrity:

```
Event 1: hash1 = SHA256(event_data1 + "")
Event 2: hash2 = SHA256(event_data2 + hash1)
Event 3: hash3 = SHA256(event_data3 + hash2)
```

Each event's `prev_hash` must match the previous event's `hash`. Any modification to past events will break the chain.

### PostgreSQL function for verification:
```sql
SELECT * FROM verify_audit_chain_integrity(start_id := 1, end_id := 100);
```

Returns rows only if integrity issues are found.

---

## Append-Only Protection

A PostgreSQL trigger prevents modification or deletion of audit records:

```sql
UPDATE audit_events SET ... -- ERROR: Update operation forbidden
DELETE FROM audit_events WHERE ... -- ERROR: Delete operation forbidden
```

This ensures the audit log is tamper-proof.

---

## Best Practices

1. **Regular Verification**: Run chain verification weekly or after security incidents
2. **Export & Archive**: Export logs monthly for long-term storage
3. **Monitor Statistics**: Check `events_last_24h` for unusual activity
4. **Filter Wisely**: Use scope and event_type filters to narrow searches
5. **Precinct Tracking**: Use `/precinct/{id}/history` for election day monitoring

---

## Troubleshooting

### No events returned
- Check authentication token (must be ADMIN or COORD)
- Verify date range (use ISO format: `2025-01-26T00:00:00`)
- Check if middleware is enabled in `app/main.py`

### Chain verification fails
- Run PostgreSQL function: `SELECT * FROM verify_audit_chain_integrity();`
- Check for manual database modifications
- Investigate events with `status: "broken"` in response

### Export limit reached
- Narrow date range
- Use multiple export calls with different ranges
- Maximum 10,000 records per export

---

## See Also

- [TASK10_AUDIT_COMPLETED.md](./TASK10_AUDIT_COMPLETED.md) - Full implementation details
- [app/audit.py](./app/audit.py) - Audit utilities
- [app/routes_audit.py](./app/routes_audit.py) - API endpoints
- [database/migration_audit.sql](./database/migration_audit.sql) - Database schema
