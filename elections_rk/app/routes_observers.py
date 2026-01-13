# API для координаторов и наблюдателей (Tasks #3-4)
# Управление профилями, заявками, назначение на УИК

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import hashlib

from app.database import get_db
from app.routes_auth import get_current_user, require_role
from app.models_extended import (
    User, ObserverProfile, ObserverApplication, ObserverCheckin,
    ObserverLegalType, ObserverStatus, ApplicationStatus, ApplicationSource, ShiftType
)

router = APIRouter(prefix="/api/observers", tags=["Observers"])


# ==================== PYDANTIC SCHEMAS ====================

class ObserverProfileCreate(BaseModel):
    legal_type: str  # ORG, DELEGATE, INDEPENDENT
    org_id: Optional[int] = None
    id_doc_type: str
    id_doc_number: str


class ObserverProfileUpdate(BaseModel):
    training_passed: Optional[bool] = None
    training_score: Optional[int] = None
    status: Optional[str] = None  # VERIFIED, REJECTED, etc.


class ObserverProfileResponse(BaseModel):
    id: int
    user_id: int
    legal_type: str
    org_id: Optional[int]
    id_doc_number: str
    training_passed: bool
    training_score: Optional[int]
    rating: float
    risk_score: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    precinct_id: int
    source: str  # ORG, SELF, NGO
    priority: int = 0
    shift: str = "FULL"  # FULL, MORNING, EVENING


class ApplicationUpdate(BaseModel):
    status: str  # ASSIGNED, RESERVE, CANCELLED
    assigned_by: Optional[int] = None


class ApplicationResponse(BaseModel):
    id: int
    observer_id: int
    precinct_id: int
    source: str
    priority: int
    shift: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CheckinCreate(BaseModel):
    precinct_id: int
    qrcode_token: str
    selfie_file: Optional[str] = None
    geo_lat: Optional[float] = None
    geo_lon: Optional[float] = None


# ==================== ПРОФИЛИ НАБЛЮДАТЕЛЕЙ ====================

@router.get("/me/profile", response_model=ObserverProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить свой профиль наблюдателя"""
    profile = db.query(ObserverProfile).filter(
        ObserverProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Observer profile not found")
    
    return profile


@router.post("/me/profile", response_model=ObserverProfileResponse)
async def create_my_profile(
    data: ObserverProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создать профиль наблюдателя (для себя)"""
    # Проверка что профиль ещё не существует
    existing = db.query(ObserverProfile).filter(
        ObserverProfile.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    # Создание профиля
    profile = ObserverProfile(
        user_id=current_user.id,
        legal_type=data.legal_type,
        org_id=data.org_id,
        id_doc_type=data.id_doc_type,
        id_doc_number=data.id_doc_number,
        status=ObserverStatus.DRAFT,
        rating=0.0,
        risk_score=0.0
    )
    
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return profile


@router.put("/me/profile", response_model=ObserverProfileResponse)
async def update_my_profile(
    data: ObserverProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновить свой профиль"""
    profile = db.query(ObserverProfile).filter(
        ObserverProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Обновление разрешённых полей
    if data.training_passed is not None:
        profile.training_passed = data.training_passed
    if data.training_score is not None:
        profile.training_score = data.training_score
    
    db.commit()
    db.refresh(profile)
    
    return profile


@router.get("/profiles", response_model=List[ObserverProfileResponse])
async def list_profiles(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Список всех профилей наблюдателей (для админов/координаторов)"""
    query = db.query(ObserverProfile)
    
    if status:
        query = query.filter(ObserverProfile.status == status)
    
    profiles = query.offset(skip).limit(limit).all()
    return profiles


@router.put("/profiles/{profile_id}/verify")
async def verify_profile(
    profile_id: int,
    data: ObserverProfileUpdate,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Верифицировать профиль наблюдателя (админ/координатор)"""
    profile = db.query(ObserverProfile).filter(ObserverProfile.id == profile_id).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Обновление статуса
    if data.status:
        profile.status = data.status
        profile.verified_by = current_user.id
        profile.verified_at = datetime.utcnow()
    
    db.commit()
    db.refresh(profile)
    
    return {"message": "Profile updated", "profile_id": profile_id, "status": profile.status}


# ==================== ЗАЯВКИ НА УИК ====================

@router.get("/me/applications", response_model=List[ApplicationResponse])
async def get_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Мои заявки на УИК"""
    profile = db.query(ObserverProfile).filter(
        ObserverProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Observer profile not found")
    
    applications = db.query(ObserverApplication).filter(
        ObserverApplication.observer_id == profile.id
    ).all()
    
    return applications


@router.post("/me/applications", response_model=ApplicationResponse)
async def create_application(
    data: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Подать заявку на УИК"""
    profile = db.query(ObserverProfile).filter(
        ObserverProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Observer profile not found")
    
    if profile.status != ObserverStatus.VERIFIED:
        raise HTTPException(status_code=403, detail="Profile must be verified")
    
    # Проверка дубликатов
    existing = db.query(ObserverApplication).filter(
        and_(
            ObserverApplication.observer_id == profile.id,
            ObserverApplication.precinct_id == data.precinct_id,
            ObserverApplication.status.in_(['REQUESTED', 'ASSIGNED'])
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Application already exists")
    
    # Создание заявки
    application = ObserverApplication(
        observer_id=profile.id,
        precinct_id=data.precinct_id,
        source=data.source,
        priority=data.priority,
        shift=data.shift,
        status=ApplicationStatus.REQUESTED
    )
    
    db.add(application)
    db.commit()
    db.refresh(application)
    
    return application


@router.get("/applications", response_model=List[ApplicationResponse])
async def list_applications(
    precinct_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Список заявок (для координаторов)"""
    query = db.query(ObserverApplication)
    
    if precinct_id:
        query = query.filter(ObserverApplication.precinct_id == precinct_id)
    if status:
        query = query.filter(ObserverApplication.status == status)
    
    applications = query.offset(skip).limit(limit).all()
    return applications


@router.put("/applications/{application_id}/assign")
async def assign_application(
    application_id: int,
    data: ApplicationUpdate,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Назначить наблюдателя на УИК (координатор)"""
    application = db.query(ObserverApplication).filter(
        ObserverApplication.id == application_id
    ).first()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Обновление статуса
    application.status = data.status
    application.assigned_by = current_user.id
    application.assigned_at = datetime.utcnow()
    
    db.commit()
    db.refresh(application)
    
    return {
        "message": "Application updated",
        "application_id": application_id,
        "status": application.status
    }


@router.get("/precincts/{precinct_id}/slots")
async def get_precinct_slots(
    precinct_id: int,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Получить статистику слотов на УИК"""
    # Подсчёт заявок по статусам
    assigned_count = db.query(func.count(ObserverApplication.id)).filter(
        and_(
            ObserverApplication.precinct_id == precinct_id,
            ObserverApplication.status == ApplicationStatus.ASSIGNED
        )
    ).scalar()
    
    requested_count = db.query(func.count(ObserverApplication.id)).filter(
        and_(
            ObserverApplication.precinct_id == precinct_id,
            ObserverApplication.status == ApplicationStatus.REQUESTED
        )
    ).scalar()
    
    reserve_count = db.query(func.count(ObserverApplication.id)).filter(
        and_(
            ObserverApplication.precinct_id == precinct_id,
            ObserverApplication.status == ApplicationStatus.RESERVE
        )
    ).scalar()
    
    return {
        "precinct_id": precinct_id,
        "assigned": assigned_count,
        "requested": requested_count,
        "reserve": reserve_count,
        "available_slots": max(0, 5 - assigned_count)  # Обычно 5 наблюдателей на УИК
    }


# ==================== ЧЕК-ИНЫ ====================

@router.post("/me/checkin")
async def create_checkin(
    data: CheckinCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Чек-ин на УИК через QR"""
    profile = db.query(ObserverProfile).filter(
        ObserverProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Observer profile not found")
    
    # Проверка что есть назначение на этот УИК
    application = db.query(ObserverApplication).filter(
        and_(
            ObserverApplication.observer_id == profile.id,
            ObserverApplication.precinct_id == data.precinct_id,
            ObserverApplication.status == ApplicationStatus.ASSIGNED
        )
    ).first()
    
    if not application:
        raise HTTPException(status_code=403, detail="Not assigned to this precinct")
    
    # Хеш селфи
    selfie_hash = None
    if data.selfie_file:
        selfie_hash = hashlib.sha256(data.selfie_file.encode()).hexdigest()
    
    # Создание чек-ина
    checkin = ObserverCheckin(
        observer_id=profile.id,
        precinct_id=data.precinct_id,
        qrcode_token=data.qrcode_token,
        selfie_hash=selfie_hash,
        geo_lat=data.geo_lat,
        geo_lon=data.geo_lon
    )
    
    db.add(checkin)
    
    # Обновление статуса заявки
    application.status = ApplicationStatus.CHECKED_IN
    
    db.commit()
    db.refresh(checkin)
    
    return {
        "message": "Check-in successful",
        "checkin_id": checkin.id,
        "precinct_id": data.precinct_id,
        "ts_in": checkin.ts_in
    }


@router.get("/precincts/{precinct_id}/checkins")
async def get_precinct_checkins(
    precinct_id: int,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Список чек-инов на УИК"""
    checkins = db.query(ObserverCheckin).filter(
        ObserverCheckin.precinct_id == precinct_id
    ).all()
    
    return {
        "precinct_id": precinct_id,
        "total_checkins": len(checkins),
        "checkins": [
            {
                "id": c.id,
                "observer_id": c.observer_id,
                "ts_in": c.ts_in,
                "ts_out": c.ts_out,
                "geo_lat": c.geo_lat,
                "geo_lon": c.geo_lon
            }
            for c in checkins
        ]
    }


# ==================== СТАТИСТИКА ====================

@router.get("/stats/summary")
async def get_observer_stats(
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Общая статистика по наблюдателям"""
    total_observers = db.query(func.count(ObserverProfile.id)).scalar()
    
    verified = db.query(func.count(ObserverProfile.id)).filter(
        ObserverProfile.status == ObserverStatus.VERIFIED
    ).scalar()
    
    pending = db.query(func.count(ObserverProfile.id)).filter(
        ObserverProfile.status == ObserverStatus.PENDING
    ).scalar()
    
    total_applications = db.query(func.count(ObserverApplication.id)).scalar()
    
    assigned = db.query(func.count(ObserverApplication.id)).filter(
        ObserverApplication.status == ApplicationStatus.ASSIGNED
    ).scalar()
    
    total_checkins = db.query(func.count(ObserverCheckin.id)).scalar()
    
    return {
        "observers": {
            "total": total_observers,
            "verified": verified,
            "pending": pending
        },
        "applications": {
            "total": total_applications,
            "assigned": assigned
        },
        "checkins": {
            "total": total_checkins
        }
    }
