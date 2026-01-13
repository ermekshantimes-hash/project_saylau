# API для агрегации результатов и подсчёта голосов (Task #7)
# Real-time агрегаты, precinct tallies, версионирование

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from pydantic import BaseModel
from typing import List, Optional, Dict, cast
from datetime import datetime

from app.database import get_db
from app.routes_auth import get_current_user, require_role
from app.models_extended import (
    User, Protocol, ProtocolItem, PrecinctTally, Candidate,
    TallyBasis, TallyStatus, ProtocolStatus
)
from app.models import Precinct, Region, Election

router = APIRouter(prefix="/api/results", tags=["Results & Aggregation"])


# ==================== SCHEMAS ====================

class TallyCreate(BaseModel):
    precinct_id: int
    candidate_id: int
    votes: int
    protocol_id: Optional[int] = None
    basis: str = "PROTOCOL"  # PROTOCOL, CORRECTION


class TallyResponse(BaseModel):
    id: int
    precinct_id: int
    candidate_id: int
    votes: int
    status: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


class AggregateResponse(BaseModel):
    candidate_id: int
    candidate_name: str
    total_votes: int
    percentage: float


# ==================== ПОДСЧЁТ (TALLY) ====================

@router.post("/tallies")
async def create_tally(
    data: TallyCreate,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Создать запись подсчёта голосов (координатор)"""
    # Проверка существующей версии
    existing = db.query(PrecinctTally).filter(
        and_(
            PrecinctTally.precinct_id == data.precinct_id,
            PrecinctTally.candidate_id == data.candidate_id,
            PrecinctTally.status == TallyStatus.VERIFIED
        )
    ).order_by(desc(PrecinctTally.version)).first()
    
    version = (existing.version + 1) if existing else 1
    
    # Создание новой записи
    tally = PrecinctTally(
        precinct_id=data.precinct_id,
        candidate_id=data.candidate_id,
        votes=data.votes,
        basis=data.basis,
        protocol_id=data.protocol_id,
        status=TallyStatus.PRELIM,
        version=version
    )
    
    db.add(tally)
    db.commit()
    db.refresh(tally)
    
    return tally


@router.post("/tallies/from-protocol/{protocol_id}")
async def create_tallies_from_protocol(
    protocol_id: int,
    current_user: User = Depends(require_role(["ADMIN", "COORD"])),
    db: Session = Depends(get_db)
):
    """Автоматическое создание подсчётов из протокола"""
    # Проверка протокола
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    if cast(ProtocolStatus, protocol.status) != ProtocolStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Protocol must be verified first")
    
    # Получить строки протокола
    items = db.query(ProtocolItem).filter(ProtocolItem.protocol_id == protocol_id).all()
    
    if not items:
        raise HTTPException(status_code=400, detail="Protocol has no items")
    
    # Получить существующие версии одним запросом (оптимизация N+1)
    candidate_ids = [item.candidate_id for item in items]
    existing_tallies = db.query(PrecinctTally).filter(
        and_(
            PrecinctTally.precinct_id == protocol.precinct_id,
            PrecinctTally.candidate_id.in_(candidate_ids)
        )
    ).all()
    
    # Создать словарь версий для быстрого доступа
    version_map = {}
    for tally in existing_tallies:
        if tally.candidate_id not in version_map:
            version_map[tally.candidate_id] = tally.version
        else:
            version_map[tally.candidate_id] = max(version_map[tally.candidate_id], tally.version)
    
    created_tallies = []
    
    for item in items:
        # Получить версию из кэша
        version = version_map.get(item.candidate_id, 0) + 1
        
        # Создание tally
        tally = PrecinctTally(
            precinct_id=protocol.precinct_id,
            candidate_id=item.candidate_id,
            votes=item.votes,
            basis=TallyBasis.PROTOCOL,
            protocol_id=protocol_id,
            status=TallyStatus.VERIFIED,
            version=version
        )
        
        db.add(tally)
        created_tallies.append(tally)
    
    db.commit()
    
    return {
        "message": f"Created {len(created_tallies)} tallies from protocol",
        "protocol_id": protocol_id,
        "precinct_id": protocol.precinct_id,
        "tallies_count": len(created_tallies)
    }


@router.get("/tallies/precinct/{precinct_id}")
async def get_precinct_tallies(
    precinct_id: int,
    db: Session = Depends(get_db)
):
    """Получить подсчёты по УИК (последние версии)"""
    # Получить последние версии для каждого кандидата
    subquery = db.query(
        PrecinctTally.candidate_id,
        func.max(PrecinctTally.version).label('max_version')
    ).filter(
        PrecinctTally.precinct_id == precinct_id
    ).group_by(PrecinctTally.candidate_id).subquery()
    
    tallies = db.query(PrecinctTally).join(
        subquery,
        and_(
            PrecinctTally.candidate_id == subquery.c.candidate_id,
            PrecinctTally.version == subquery.c.max_version,
            PrecinctTally.precinct_id == precinct_id
        )
    ).all()
    
    # Получить имена кандидатов
    result = []
    for tally in tallies:
        candidate = db.query(Candidate).filter(Candidate.id == tally.candidate_id).first()
        result.append({
            "candidate_id": tally.candidate_id,
            "candidate_name": candidate.name if candidate else "Unknown",
            "votes": tally.votes,
            "status": tally.status.value if hasattr(tally.status, 'value') else str(tally.status),
            "version": tally.version
        })
    
    return {
        "precinct_id": precinct_id,
        "tallies": result,
        "total_votes": sum(t["votes"] for t in result)
    }


# ==================== АГРЕГАЦИЯ ====================

@router.get("/aggregate/country")
async def aggregate_country(
    db: Session = Depends(get_db)
):
    """Агрегация по всей стране"""
    # Получить последние версии tallies
    subquery = db.query(
        PrecinctTally.precinct_id,
        PrecinctTally.candidate_id,
        func.max(PrecinctTally.version).label('max_version')
    ).filter(
        PrecinctTally.status == TallyStatus.VERIFIED
    ).group_by(PrecinctTally.precinct_id, PrecinctTally.candidate_id).subquery()
    
    # Суммировать голоса
    aggregates = db.query(
        Candidate.id,
        Candidate.name,
        func.sum(PrecinctTally.votes).label('total_votes')
    ).join(
        PrecinctTally,
        Candidate.id == PrecinctTally.candidate_id
    ).join(
        subquery,
        and_(
            PrecinctTally.precinct_id == subquery.c.precinct_id,
            PrecinctTally.candidate_id == subquery.c.candidate_id,
            PrecinctTally.version == subquery.c.max_version
        )
    ).group_by(Candidate.id, Candidate.name).all()
    
    # Подсчёт процентов
    total_votes = sum(a.total_votes for a in aggregates)
    
    results = [
        {
            "candidate_id": a.id,
            "candidate_name": a.name,
            "total_votes": a.total_votes,
            "percentage": round((a.total_votes / total_votes * 100) if total_votes > 0 else 0, 2)
        }
        for a in aggregates
    ]
    
    # Сортировка по голосам
    results.sort(key=lambda x: x["total_votes"], reverse=True)
    
    # Подсчёт охвата
    total_precincts = db.query(func.count(Precinct.id)).scalar()
    precincts_with_results = db.query(
        func.count(func.distinct(PrecinctTally.precinct_id))
    ).filter(PrecinctTally.status == TallyStatus.VERIFIED).scalar()
    
    return {
        "level": "country",
        "total_votes": total_votes,
        "total_precincts": total_precincts,
        "precincts_with_results": precincts_with_results,
        "coverage_percent": round((precincts_with_results / total_precincts * 100) if total_precincts > 0 else 0, 2),
        "results": results
    }


@router.get("/aggregate/region/{region_id}")
async def aggregate_region(
    region_id: int,
    db: Session = Depends(get_db)
):
    """Агрегация по региону"""
    # Получить все районы региона
    districts = db.query(Region.id).filter(Region.parent_id == region_id).all()
    district_ids = [d.id for d in districts]
    
    if not district_ids:
        # Если нет районов, значит это сам район
        district_ids = [region_id]
    
    # Получить УИК в районах
    precincts = db.query(Precinct.id).filter(Precinct.region_id.in_(district_ids)).all()
    precinct_ids = [p.id for p in precincts]
    
    # Агрегация по УИК региона
    subquery = db.query(
        PrecinctTally.precinct_id,
        PrecinctTally.candidate_id,
        func.max(PrecinctTally.version).label('max_version')
    ).filter(
        and_(
            PrecinctTally.precinct_id.in_(precinct_ids),
            PrecinctTally.status == TallyStatus.VERIFIED
        )
    ).group_by(PrecinctTally.precinct_id, PrecinctTally.candidate_id).subquery()
    
    aggregates = db.query(
        Candidate.id,
        Candidate.name,
        func.sum(PrecinctTally.votes).label('total_votes')
    ).join(
        PrecinctTally,
        Candidate.id == PrecinctTally.candidate_id
    ).join(
        subquery,
        and_(
            PrecinctTally.precinct_id == subquery.c.precinct_id,
            PrecinctTally.candidate_id == subquery.c.candidate_id,
            PrecinctTally.version == subquery.c.max_version
        )
    ).group_by(Candidate.id, Candidate.name).all()
    
    total_votes = sum(a.total_votes for a in aggregates)
    
    results = [
        {
            "candidate_id": a.id,
            "candidate_name": a.name,
            "total_votes": a.total_votes,
            "percentage": round((a.total_votes / total_votes * 100) if total_votes > 0 else 0, 2)
        }
        for a in aggregates
    ]
    
    results.sort(key=lambda x: x["total_votes"], reverse=True)
    
    # Охват
    total_precincts = len(precinct_ids)
    precincts_with_results = db.query(
        func.count(func.distinct(PrecinctTally.precinct_id))
    ).filter(
        and_(
            PrecinctTally.precinct_id.in_(precinct_ids),
            PrecinctTally.status == TallyStatus.VERIFIED
        )
    ).scalar()
    
    # Название региона
    region = db.query(Region).filter(Region.id == region_id).first()
    
    return {
        "level": "region",
        "region_id": region_id,
        "region_name": region.name if region else "Unknown",
        "total_votes": total_votes,
        "total_precincts": total_precincts,
        "precincts_with_results": precincts_with_results,
        "coverage_percent": round((precincts_with_results / total_precincts * 100) if total_precincts > 0 else 0, 2),
        "results": results
    }


@router.get("/aggregate/top-regions")
async def aggregate_top_regions(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """ТОП регионов по количеству проголосовавших"""
    # Получить регионы верхнего уровня
    regions = db.query(Region).filter(Region.parent_id.is_(None)).all()
    
    results = []
    
    for region in regions:
        # Районы региона
        districts = db.query(Region.id).filter(Region.parent_id == region.id).all()
        district_ids = [d.id for d in districts] if districts else [region.id]
        
        # УИК
        precincts = db.query(Precinct.id).filter(Precinct.region_id.in_(district_ids)).all()
        precinct_ids = [p.id for p in precincts]
        
        # Подсчёт голосов
        total_votes = db.query(
            func.sum(PrecinctTally.votes)
        ).join(
            db.query(
                PrecinctTally.precinct_id,
                PrecinctTally.candidate_id,
                func.max(PrecinctTally.version).label('max_version')
            ).filter(
                and_(
                    PrecinctTally.precinct_id.in_(precinct_ids),
                    PrecinctTally.status == TallyStatus.VERIFIED
                )
            ).group_by(PrecinctTally.precinct_id, PrecinctTally.candidate_id).subquery(),
            and_(
                PrecinctTally.precinct_id == db.query(
                    PrecinctTally.precinct_id
                ).filter(PrecinctTally.precinct_id.in_(precinct_ids)).subquery().c.precinct_id
            )
        ).scalar() or 0
        
        results.append({
            "region_id": region.id,
            "region_name": region.name,
            "total_votes": total_votes,
            "total_precincts": len(precinct_ids)
        })
    
    # Сортировка
    results.sort(key=lambda x: x["total_votes"], reverse=True)
    
    return {
        "top_regions": results[:limit]
    }


# ==================== СТАТИСТИКА ====================

@router.get("/stats/summary")
async def get_results_stats(
    db: Session = Depends(get_db)
):
    """Общая статистика результатов"""
    total_precincts = db.query(func.count(Precinct.id)).scalar()
    
    precincts_with_protocols = db.query(
        func.count(func.distinct(Protocol.precinct_id))
    ).filter(Protocol.status == ProtocolStatus.VERIFIED).scalar()
    
    precincts_with_tallies = db.query(
        func.count(func.distinct(PrecinctTally.precinct_id))
    ).filter(PrecinctTally.status == TallyStatus.VERIFIED).scalar()
    
    total_votes = db.query(func.sum(PrecinctTally.votes)).join(
        db.query(
            PrecinctTally.precinct_id,
            PrecinctTally.candidate_id,
            func.max(PrecinctTally.version).label('max_version')
        ).filter(
            PrecinctTally.status == TallyStatus.VERIFIED
        ).group_by(PrecinctTally.precinct_id, PrecinctTally.candidate_id).subquery(),
        and_(
            PrecinctTally.precinct_id == db.query(PrecinctTally.precinct_id).subquery().c.precinct_id
        )
    ).scalar() or 0
    
    return {
        "total_precincts": total_precincts,
        "precincts_with_protocols": precincts_with_protocols,
        "precincts_with_tallies": precincts_with_tallies,
        "coverage_percent": round((precincts_with_tallies / total_precincts * 100) if total_precincts > 0 else 0, 2),
        "total_votes": total_votes
    }
