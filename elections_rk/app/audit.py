# Middleware и утилиты для аудит-логирования (Task #10)
# Append-only лог с hash chains

from fastapi import Request
from sqlalchemy.orm import Session
from datetime import datetime
import hashlib
import json
from typing import Optional

from app.database import SessionLocal
from app.models_extended import AuditEvent, AuditScope


def generate_event_hash(event_data: dict, prev_hash: Optional[str] = None) -> str:
    """
    Генерация SHA256 хеша события для цепочки
    """
    # Сериализуем данные события
    event_str = json.dumps(event_data, sort_keys=True, default=str)
    
    # Добавляем предыдущий хеш для цепочки
    chain_str = event_str + (prev_hash or "")
    
    # Хешируем
    return hashlib.sha256(chain_str.encode()).hexdigest()


def log_audit_event(
    actor_user_id: Optional[int],
    scope: str,
    event_type: str,
    payload: dict,
    db: Session
):
    """
    Создать запись в аудит-логе
    """
    # Получить последний хеш в цепочке
    last_event = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
    prev_hash = last_event.hash if last_event else None
    
    # Создать данные события
    event_data = {
        "actor_user_id": actor_user_id,
        "scope": scope,
        "event_type": event_type,
        "payload": payload,
        "ts": datetime.utcnow().isoformat()
    }
    
    # Сгенерировать хеш
    event_hash = generate_event_hash(event_data, prev_hash)
    
    # Создать запись
    audit_event = AuditEvent(
        actor_user_id=actor_user_id,
        scope=scope,
        event_type=event_type,
        payload_json=payload,
        ts=datetime.utcnow(),
        hash=event_hash,
        prev_hash=prev_hash
    )
    
    db.add(audit_event)
    db.commit()
    
    return audit_event


async def audit_middleware(request: Request, call_next):
    """
    Middleware для автоматического логирования API запросов
    """
    # Исключаем статичные файлы и healthcheck
    if request.url.path.startswith("/static") or request.url.path == "/health":
        return await call_next(request)
    
    # Получаем user_id из токена (если есть)
    user_id = None
    if hasattr(request.state, "user"):
        user_id = request.state.user.id
    
    # Выполняем запрос
    response = await call_next(request)
    
    # Логируем только определённые методы и пути
    should_log = (
        request.method in ["POST", "PUT", "DELETE"] and
        any(path in request.url.path for path in [
            "/api/auth/",
            "/api/observers/",
            "/api/protocols/",
            "/api/incidents/",
            "/api/results/"
        ])
    )
    
    if should_log and response.status_code < 400:
        # Создаём запись в аудите асинхронно
        db = SessionLocal()
        try:
            log_audit_event(
                actor_user_id=user_id,
                scope=AuditScope.USER if user_id else AuditScope.SYSTEM,
                event_type=f"{request.method}:{request.url.path}",
                payload={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "ip": request.client.host if request.client else None
                },
                db=db
            )
        finally:
            db.close()
    
    return response


def verify_audit_chain(db: Session, start_id: Optional[int] = None, end_id: Optional[int] = None) -> dict:
    """
    Верификация целостности цепочки аудит-логов
    Возвращает статистику проверки
    """
    query = db.query(AuditEvent).order_by(AuditEvent.id)
    
    if start_id:
        query = query.filter(AuditEvent.id >= start_id)
    if end_id:
        query = query.filter(AuditEvent.id <= end_id)
    
    events = query.all()
    
    if not events:
        return {"status": "empty", "message": "No audit events found"}
    
    # Проверка цепочки
    prev_hash = None
    broken_events = []
    
    for event in events:
        # Проверяем что prev_hash совпадает
        if event.prev_hash != prev_hash:
            broken_events.append({
                "id": event.id,
                "expected_prev_hash": prev_hash,
                "actual_prev_hash": event.prev_hash
            })
        
        # Пересчитываем хеш события
        event_data = {
            "actor_user_id": event.actor_user_id,
            "scope": event.scope.value if hasattr(event.scope, 'value') else str(event.scope),
            "event_type": event.event_type,
            "payload": event.payload_json,
            "ts": event.ts.isoformat()
        }
        
        calculated_hash = generate_event_hash(event_data, event.prev_hash)
        
        # Проверяем целостность хеша
        if calculated_hash != event.hash:
            broken_events.append({
                "id": event.id,
                "reason": "hash_mismatch",
                "expected_hash": calculated_hash,
                "actual_hash": event.hash
            })
        
        prev_hash = event.hash
    
    if broken_events:
        return {
            "status": "broken",
            "message": f"Found {len(broken_events)} broken events",
            "total_events": len(events),
            "broken_events": broken_events
        }
    else:
        return {
            "status": "valid",
            "message": "Audit chain is valid",
            "total_events": len(events),
            "first_event_id": events[0].id,
            "last_event_id": events[-1].id
        }


# Утилиты для логирования специфичных событий

def log_user_login(user_id: int, ip: str, db: Session):
    """Лог входа пользователя"""
    log_audit_event(
        actor_user_id=user_id,
        scope=AuditScope.USER,
        event_type="USER_LOGIN",
        payload={"ip": ip},
        db=db
    )


def log_profile_verification(verifier_id: int, profile_id: int, status: str, db: Session):
    """Лог верификации профиля"""
    log_audit_event(
        actor_user_id=verifier_id,
        scope=AuditScope.USER,
        event_type="PROFILE_VERIFIED",
        payload={"profile_id": profile_id, "status": status},
        db=db
    )


def log_protocol_upload(uploader_id: int, protocol_id: int, precinct_id: int, db: Session):
    """Лог загрузки протокола"""
    log_audit_event(
        actor_user_id=uploader_id,
        scope=AuditScope.USER,
        event_type="PROTOCOL_UPLOADED",
        payload={"protocol_id": protocol_id, "precinct_id": precinct_id},
        db=db
    )


def log_protocol_verification(verifier_id: int, protocol_id: int, status: str, db: Session):
    """Лог верификации протокола"""
    log_audit_event(
        actor_user_id=verifier_id,
        scope=AuditScope.USER,
        event_type="PROTOCOL_VERIFIED",
        payload={"protocol_id": protocol_id, "status": status},
        db=db
    )


def log_tally_created(creator_id: int, tally_id: int, precinct_id: int, votes: int, db: Session):
    """Лог создания подсчёта"""
    log_audit_event(
        actor_user_id=creator_id,
        scope=AuditScope.USER,
        event_type="TALLY_CREATED",
        payload={
            "tally_id": tally_id,
            "precinct_id": precinct_id,
            "votes": votes
        },
        db=db
    )


def log_incident_created(reporter_id: int, incident_id: int, precinct_id: int, severity: str, db: Session):
    """Лог создания инцидента"""
    log_audit_event(
        actor_user_id=reporter_id,
        scope=AuditScope.USER,
        event_type="INCIDENT_CREATED",
        payload={
            "incident_id": incident_id,
            "precinct_id": precinct_id,
            "severity": severity
        },
        db=db
    )


def log_system_event(event_type: str, payload: dict, db: Session):
    """Лог системного события"""
    log_audit_event(
        actor_user_id=None,
        scope=AuditScope.SYSTEM,
        event_type=event_type,
        payload=payload,
        db=db
    )
