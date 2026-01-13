# API endpoints для аудит-логов (Task #10)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models_extended import AuditEvent, User, AuditScope
from app.routes_auth import get_current_user, require_role
from app.audit import verify_audit_chain, log_system_event

router = APIRouter(prefix="/api/audit", tags=["Audit"])


# Schemas
class AuditEventResponse(BaseModel):
    id: int
    actor_user_id: Optional[int]
    actor_name: Optional[str]  # ФИО из User
    scope: str
    event_type: str
    payload_json: dict
    ts: datetime
    hash: str
    prev_hash: Optional[str]
    
    class Config:
        from_attributes = True


class AuditStatsResponse(BaseModel):
    total_events: int
    events_last_24h: int
    events_last_7d: int
    events_by_scope: dict
    events_by_type_top10: list
    first_event_ts: Optional[datetime]
    last_event_ts: Optional[datetime]


class ChainVerifyResponse(BaseModel):
    status: str
    message: str
    total_events: int
    broken_events: Optional[list] = None
    first_event_id: Optional[int] = None
    last_event_id: Optional[int] = None


# Endpoints

@router.get("/events", response_model=List[AuditEventResponse])
def get_audit_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    scope: Optional[str] = None,
    event_type: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить список аудит-событий с фильтрами
    Только ADMIN и COORD
    """
    query = db.query(AuditEvent).order_by(AuditEvent.id.desc())
    
    # Фильтры
    if scope:
        query = query.filter(AuditEvent.scope == scope)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if actor_user_id:
        query = query.filter(AuditEvent.actor_user_id == actor_user_id)
    if start_date:
        query = query.filter(AuditEvent.ts >= start_date)
    if end_date:
        query = query.filter(AuditEvent.ts <= end_date)
    
    total = query.count()
    events = query.offset(skip).limit(limit).all()
    
    # Обогащаем данными о пользователях
    result = []
    for event in events:
        event_dict = {
            "id": event.id,
            "actor_user_id": event.actor_user_id,
            "actor_name": None,
            "scope": event.scope.value if hasattr(event.scope, 'value') else str(event.scope),
            "event_type": event.event_type,
            "payload_json": event.payload_json,
            "ts": event.ts,
            "hash": event.hash,
            "prev_hash": event.prev_hash
        }
        
        # Получить имя актёра
        if event.actor_user_id:
            user = db.query(User).filter(User.id == event.actor_user_id).first()
            if user:
                event_dict["actor_name"] = user.full_name
        
        result.append(AuditEventResponse(**event_dict))
    
    return result


@router.get("/events/{event_id}", response_model=AuditEventResponse)
def get_audit_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить детали аудит-события
    """
    event = db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    
    event_dict = {
        "id": event.id,
        "actor_user_id": event.actor_user_id,
        "actor_name": None,
        "scope": event.scope.value if hasattr(event.scope, 'value') else str(event.scope),
        "event_type": event.event_type,
        "payload_json": event.payload_json,
        "ts": event.ts,
        "hash": event.hash,
        "prev_hash": event.prev_hash
    }
    
    if event.actor_user_id:
        user = db.query(User).filter(User.id == event.actor_user_id).first()
        if user:
            event_dict["actor_name"] = user.full_name
    
    return AuditEventResponse(**event_dict)


@router.get("/stats", response_model=AuditStatsResponse)
def get_audit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Статистика аудит-логов
    Только ADMIN
    """
    now = datetime.utcnow()
    
    # Общее количество
    total = db.query(func.count(AuditEvent.id)).scalar()
    
    # За последние 24 часа
    last_24h = db.query(func.count(AuditEvent.id)).filter(
        AuditEvent.ts >= now - timedelta(hours=24)
    ).scalar()
    
    # За последние 7 дней
    last_7d = db.query(func.count(AuditEvent.id)).filter(
        AuditEvent.ts >= now - timedelta(days=7)
    ).scalar()
    
    # По scope
    by_scope = db.query(
        AuditEvent.scope,
        func.count(AuditEvent.id).label("count")
    ).group_by(AuditEvent.scope).all()
    
    scope_dict = {
        str(scope): count for scope, count in by_scope
    }
    
    # Топ-10 типов событий
    by_type = db.query(
        AuditEvent.event_type,
        func.count(AuditEvent.id).label("count")
    ).group_by(AuditEvent.event_type).order_by(
        func.count(AuditEvent.id).desc()
    ).limit(10).all()
    
    type_list = [
        {"event_type": event_type, "count": count}
        for event_type, count in by_type
    ]
    
    # Временной диапазон
    first_event = db.query(AuditEvent).order_by(AuditEvent.id).first()
    last_event = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
    
    return AuditStatsResponse(
        total_events=total or 0,
        events_last_24h=last_24h or 0,
        events_last_7d=last_7d or 0,
        events_by_scope=scope_dict,
        events_by_type_top10=type_list,
        first_event_ts=first_event.ts if first_event else None,
        last_event_ts=last_event.ts if last_event else None
    )


@router.post("/verify-chain", response_model=ChainVerifyResponse)
def verify_chain(
    start_id: Optional[int] = Query(None, description="ID начального события"),
    end_id: Optional[int] = Query(None, description="ID конечного события"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Проверить целостность цепочки аудит-логов
    Только ADMIN
    
    Проверяет:
    1. Связность prev_hash → hash
    2. Корректность пересчёта hash для каждого события
    """
    result = verify_audit_chain(db, start_id, end_id)
    
    # Логируем проверку
    log_system_event(
        event_type="AUDIT_CHAIN_VERIFY",
        payload={
            "start_id": start_id,
            "end_id": end_id,
            "result_status": result["status"],
            "total_events": result.get("total_events", 0)
        },
        db=db
    )
    
    return ChainVerifyResponse(**result)


@router.get("/user/{user_id}/history", response_model=List[AuditEventResponse])
def get_user_audit_history(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить историю действий пользователя
    Только ADMIN и COORD
    """
    # Проверяем существование пользователя
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем события
    events = db.query(AuditEvent).filter(
        AuditEvent.actor_user_id == user_id
    ).order_by(AuditEvent.id.desc()).offset(skip).limit(limit).all()
    
    result = []
    for event in events:
        result.append(AuditEventResponse(
            id=event.id,
            actor_user_id=event.actor_user_id,
            actor_name=user.full_name,
            scope=event.scope.value if hasattr(event.scope, 'value') else str(event.scope),
            event_type=event.event_type,
            payload_json=event.payload_json,
            ts=event.ts,
            hash=event.hash,
            prev_hash=event.prev_hash
        ))
    
    return result


@router.get("/precinct/{precinct_id}/history", response_model=List[AuditEventResponse])
def get_precinct_audit_history(
    precinct_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить историю событий по УИК
    Только ADMIN и COORD
    """
    # Ищем события где в payload упоминается precinct_id
    from sqlalchemy import cast, String
    
    events = db.query(AuditEvent).filter(
        cast(AuditEvent.payload_json, String).like(f'%"precinct_id": {precinct_id}%')
    ).order_by(AuditEvent.id.desc()).offset(skip).limit(limit).all()
    
    result = []
    for event in events:
        actor_name = None
        if event.actor_user_id:
            user = db.query(User).filter(User.id == event.actor_user_id).first()
            if user:
                actor_name = user.full_name
        
        result.append(AuditEventResponse(
            id=event.id,
            actor_user_id=event.actor_user_id,
            actor_name=actor_name,
            scope=event.scope.value if hasattr(event.scope, 'value') else str(event.scope),
            event_type=event.event_type,
            payload_json=event.payload_json,
            ts=event.ts,
            hash=event.hash,
            prev_hash=event.prev_hash
        ))
    
    return result


@router.get("/export", response_model=List[AuditEventResponse])
def export_audit_log(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Экспорт аудит-логов за период (максимум 10000 записей)
    Только ADMIN
    """
    query = db.query(AuditEvent).order_by(AuditEvent.id)
    
    if start_date:
        query = query.filter(AuditEvent.ts >= start_date)
    if end_date:
        query = query.filter(AuditEvent.ts <= end_date)
    
    events = query.limit(10000).all()
    
    result = []
    for event in events:
        actor_name = None
        if event.actor_user_id:
            user = db.query(User).filter(User.id == event.actor_user_id).first()
            if user:
                actor_name = user.full_name
        
        result.append(AuditEventResponse(
            id=event.id,
            actor_user_id=event.actor_user_id,
            actor_name=actor_name,
            scope=event.scope.value if hasattr(event.scope, 'value') else str(event.scope),
            event_type=event.event_type,
            payload_json=event.payload_json,
            ts=event.ts,
            hash=event.hash,
            prev_hash=event.prev_hash
        ))
    
    # Логируем экспорт
    log_system_event(
        event_type="AUDIT_LOG_EXPORT",
        payload={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "exported_count": len(result),
            "exported_by_user_id": current_user.id
        },
        db=db
    )
    
    return result
