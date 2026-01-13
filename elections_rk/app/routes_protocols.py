# API для протоколов и инцидентов (Tasks #6, #8)
# Загрузка протоколов, OCR, инциденты, модерация

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import os
import json

from app.database import get_db
from app.routes_auth import get_current_user, require_role
from app.models_extended import (
    User, ObserverProfile, Protocol, ProtocolItem, Incident,
    ProtocolStatus, ProtocolSource, IncidentType, IncidentSeverity, IncidentStatus
)
from app.models import Precinct, Election, PrecinctResult

router = APIRouter(tags=["Protocols & Incidents"])


# ==================== SCHEMAS ====================

class ProtocolUploadResponse(BaseModel):
    id: int
    precinct_id: int
    file_url: str
    file_hash: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProtocolItemCreate(BaseModel):
    candidate_id: int
    votes: int


class ProtocolVerify(BaseModel):
    status: str  # VERIFIED, REJECTED, DISPUTED
    verification_notes: Optional[str] = None


class IncidentCreate(BaseModel):
    precinct_id: int
    type: str  # BLOCK_ENTRY, DOC_TAKEN, BALLOT_STUFFING, OTHER
    severity: str  # LOW, MEDIUM, HIGH
    description: str
    media_urls: Optional[List[str]] = None


class IncidentUpdate(BaseModel):
    status: Optional[str] = None  # OPEN, IN_PROGRESS, RESOLVED
    assigned_to: Optional[int] = None
    resolution_notes: Optional[str] = None


class IncidentResponse(BaseModel):
    id: int
    precinct_id: int
    reporter_id: int
    type: str
    severity: str
    description: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== ПРОТОКОЛЫ ====================

@router.post("/api/protocols/upload")
async def upload_protocol(
    precinct_id: int = Form(...),
    election_id: int = Form(...),
    subjects_json: str = Form(...),
    meta_json: str = Form("{}"),
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(lambda: None),  # Опциональная авторизация для теста
    db: Session = Depends(get_db)
):
    """Загрузка протокола наблюдателем (с результатами)"""
    # Проверка формата
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")
    
    # Проверка существования выборов
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    # Проверка существования участка, создание если нет
    precinct = db.query(Precinct).filter(Precinct.id == precinct_id).first()
    if not precinct:
        precinct = Precinct(
            id=precinct_id,
            region_id=1,  # Default region
            precinct_number=precinct_id,
            address=f"Участок {precinct_id}",
            voters_registered=1000
        )
        db.add(precinct)
        db.flush()
    
    # Чтение файла
    file_content = await file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Сохранение файла
    upload_dir = "uploads/protocols"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_name = f"{file_hash[:16]}_{file.filename}"
    file_path = os.path.join(upload_dir, file_name)
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Создание записи протокола
    protocol = Protocol(
        precinct_id=precinct_id,
        uploader_id=current_user.id if current_user else 1,  # Default user ID для тестирования
        file_url=f"/uploads/protocols/{file_name}",
        file_hash=file_hash,
        file_size=len(file_content),
        source=ProtocolSource.PHOTO,
        status=ProtocolStatus.DRAFT,
        version=1
    )
    
    db.add(protocol)
    db.flush() # Получить ID
    
    # Обработка результатов
    try:
        subjects_data = json.loads(subjects_json)

        meta: dict = {}
        try:
            meta = json.loads(meta_json or "{}")
        except Exception:
            meta = {}
        
        for item in subjects_data:
            protocol_item = ProtocolItem(
                protocol_id=protocol.id,
                candidate_id=item['subject_id'],
                votes=item['votes']
            )
            db.add(protocol_item)
            
        protocol.status = ProtocolStatus.UNDER_REVIEW

        # Persist UI-provided structured fields (election_id + manual counts)
        protocol.ocr_json = {
            "election_id": election_id,
            "manual_fields": meta,
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid subjects data: {str(e)}")
    
    db.commit()
    db.refresh(protocol)
    
    return protocol


@router.post("/api/protocols/{protocol_id}/items")
async def add_protocol_items(
    protocol_id: int,
    items: List[ProtocolItemCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавить строки протокола (голоса по кандидатам)"""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    # Проверка прав (владелец или админ)
    if protocol.uploader_id != current_user.id and current_user.role not in ["ADMIN", "COORD"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Удаление старых строк (если есть)
    db.query(ProtocolItem).filter(ProtocolItem.protocol_id == protocol_id).delete()
    
    # Добавление новых строк
    for item in items:
        protocol_item = ProtocolItem(
            protocol_id=protocol_id,
            candidate_id=item.candidate_id,
            votes=item.votes
        )
        db.add(protocol_item)
    
    # Обновление статуса протокола
    protocol.status = ProtocolStatus.UNDER_REVIEW
    
    db.commit()
    
    return {
        "message": "Protocol items added",
        "protocol_id": protocol_id,
        "items_count": len(items)
    }


@router.get("/api/protocols")
async def list_protocols(
    precinct_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Список протоколов (для координаторов)"""
    query = db.query(Protocol)
    
    if precinct_id:
        query = query.filter(Protocol.precinct_id == precinct_id)
    if status:
        query = query.filter(Protocol.status == status)
    
    protocols = query.order_by(Protocol.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": query.count(),
        "protocols": [
            {
                "id": p.id,
                "precinct_id": p.precinct_id,
                "uploader_id": p.uploader_id,
                "file_url": p.file_url,
                "status": p.status.value if hasattr(p.status, 'value') else str(p.status),
                "created_at": p.created_at
            }
            for p in protocols
        ]
    }


@router.get("/api/protocols/{protocol_id}")
async def get_protocol(
    protocol_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Детали протокола"""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    # Получить строки протокола
    items = db.query(ProtocolItem).filter(ProtocolItem.protocol_id == protocol_id).all()
    
    return {
        "id": protocol.id,
        "precinct_id": protocol.precinct_id,
        "uploader_id": protocol.uploader_id,
        "file_url": protocol.file_url,
        "file_hash": protocol.file_hash,
        "status": protocol.status.value if hasattr(protocol.status, 'value') else str(protocol.status),
        "version": protocol.version,
        "created_at": protocol.created_at,
        "items": [
            {
                "candidate_id": item.candidate_id,
                "votes": item.votes
            }
            for item in items
        ]
    }


@router.put("/api/protocols/{protocol_id}/verify")
async def verify_protocol(
    protocol_id: int,
    data: ProtocolVerify,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Верификация протокола (координатор/админ)"""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    # Обновление статуса
    protocol.status = data.status
    protocol.verified_by = current_user.id
    protocol.verified_at = datetime.utcnow()
    
    if data.verification_notes:
        protocol.verification_notes = data.verification_notes

    # If verified, publish results into precinct_results for public aggregation.
    # election_id is stored in protocol.ocr_json on upload.
    if str(data.status).upper() == "VERIFIED":
        election_id: Optional[int] = None
        if isinstance(protocol.ocr_json, dict):
            try:
                election_id = int(protocol.ocr_json.get("election_id")) if protocol.ocr_json.get("election_id") is not None else None
            except Exception:
                election_id = None

        if election_id is None:
            raise HTTPException(status_code=400, detail="Protocol missing election_id; cannot publish results")

        # Validate election
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        items = db.query(ProtocolItem).filter(ProtocolItem.protocol_id == protocol_id).all()
        if not items:
            raise HTTPException(status_code=400, detail="Protocol has no items")

        for item in items:
            existing = db.query(PrecinctResult).filter(
                PrecinctResult.election_id == election_id,
                PrecinctResult.precinct_id == protocol.precinct_id,
                PrecinctResult.subject_id == item.candidate_id,
            ).first()

            if existing:
                existing.votes = int(item.votes)
            else:
                db.add(
                    PrecinctResult(
                        election_id=election_id,
                        precinct_id=protocol.precinct_id,
                        subject_id=item.candidate_id,
                        votes=int(item.votes),
                    )
                )
    
    db.commit()
    db.refresh(protocol)
    
    return {
        "message": "Protocol verified",
        "protocol_id": protocol_id,
        "status": protocol.status.value if hasattr(protocol.status, 'value') else str(protocol.status)
    }


# ==================== ИНЦИДЕНТЫ ====================

@router.post("/api/incidents", response_model=IncidentResponse)
async def create_incident(
    data: IncidentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создать инцидент (наблюдатель)"""
    # Проверка существования УИК
    precinct = db.query(Precinct).filter(Precinct.id == data.precinct_id).first()
    if not precinct:
        raise HTTPException(status_code=404, detail="Precinct not found")
    
    # SLA deadline (48 часов для HIGH, 72 для MEDIUM, 7 дней для LOW)
    from datetime import timedelta
    sla_hours = {"HIGH": 48, "MEDIUM": 72, "LOW": 168}
    sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours.get(data.severity, 72))
    
    # Создание инцидента
    incident = Incident(
        precinct_id=data.precinct_id,
        reporter_id=current_user.id,
        type=data.type,
        severity=data.severity,
        description=data.description,
        media_urls=data.media_urls,
        status=IncidentStatus.OPEN,
        sla_deadline=sla_deadline
    )
    
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    return incident


@router.get("/api/incidents")
async def list_incidents(
    precinct_id: Optional[int] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role(["ADMIN", "COORD", "MEDIA"])),
    db: Session = Depends(get_db)
):
    """Список инцидентов"""
    query = db.query(Incident)
    
    if precinct_id:
        query = query.filter(Incident.precinct_id == precinct_id)
    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)
    
    incidents = query.order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": query.count(),
        "incidents": [
            {
                "id": i.id,
                "precinct_id": i.precinct_id,
                "reporter_id": i.reporter_id,
                "type": i.type.value if hasattr(i.type, 'value') else str(i.type),
                "severity": i.severity.value if hasattr(i.severity, 'value') else str(i.severity),
                "description": i.description,
                "status": i.status.value if hasattr(i.status, 'value') else str(i.status),
                "sla_deadline": i.sla_deadline,
                "created_at": i.created_at
            }
            for i in incidents
        ]
    }


@router.get("/api/incidents/{incident_id}")
async def get_incident(
    incident_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Детали инцидента"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return {
        "id": incident.id,
        "precinct_id": incident.precinct_id,
        "reporter_id": incident.reporter_id,
        "type": incident.type.value if hasattr(incident.type, 'value') else str(incident.type),
        "severity": incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity),
        "description": incident.description,
        "media_urls": incident.media_urls,
        "status": incident.status.value if hasattr(incident.status, 'value') else str(incident.status),
        "sla_deadline": incident.sla_deadline,
        "assigned_to": incident.assigned_to,
        "resolution_notes": incident.resolution_notes,
        "resolved_at": incident.resolved_at,
        "created_at": incident.created_at
    }


@router.put("/api/incidents/{incident_id}")
async def update_incident(
    incident_id: int,
    data: IncidentUpdate,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Обновить инцидент (модерация)"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Обновление полей
    if data.status:
        incident.status = data.status
        if data.status == "RESOLVED":
            incident.resolved_at = datetime.utcnow()
    
    if data.assigned_to:
        incident.assigned_to = data.assigned_to
    
    if data.resolution_notes:
        incident.resolution_notes = data.resolution_notes
    
    db.commit()
    db.refresh(incident)
    
    return {
        "message": "Incident updated",
        "incident_id": incident_id,
        "status": incident.status.value if hasattr(incident.status, 'value') else str(incident.status)
    }


@router.get("/api/incidents/stats/summary")
async def get_incidents_stats(
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Статистика по инцидентам"""
    total = db.query(func.count(Incident.id)).scalar()
    
    open_count = db.query(func.count(Incident.id)).filter(
        Incident.status == IncidentStatus.OPEN
    ).scalar()
    
    in_progress = db.query(func.count(Incident.id)).filter(
        Incident.status == IncidentStatus.IN_PROGRESS
    ).scalar()
    
    resolved = db.query(func.count(Incident.id)).filter(
        Incident.status == IncidentStatus.RESOLVED
    ).scalar()
    
    # По серьёзности
    high = db.query(func.count(Incident.id)).filter(
        Incident.severity == IncidentSeverity.HIGH
    ).scalar()
    
    medium = db.query(func.count(Incident.id)).filter(
        Incident.severity == IncidentSeverity.MEDIUM
    ).scalar()
    
    low = db.query(func.count(Incident.id)).filter(
        Incident.severity == IncidentSeverity.LOW
    ).scalar()
    
    return {
        "total": total,
        "by_status": {
            "open": open_count,
            "in_progress": in_progress,
            "resolved": resolved
        },
        "by_severity": {
            "high": high,
            "medium": medium,
            "low": low
        }
    }
