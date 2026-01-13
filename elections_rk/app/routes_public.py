# Public API with rate limiting (Task #13)
# Открытый API для СМИ, НПО, исследователей

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import Election, Region, Precinct, ElectionSubject, PrecinctResult
from app.models_extended import (
    Protocol, ProtocolItem, PrecinctTally, Incident, 
    ObserverProfile, Candidate
)

# Rate limiter с in-memory storage (Redis опционален)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/hour", "200/minute"]
)

router = APIRouter(prefix="/api/public", tags=["Public API"])


# === SCHEMAS ===

class PublicElectionInfo(BaseModel):
    id: int
    name: str
    election_date: Optional[str]
    election_type: str


class PublicRegionInfo(BaseModel):
    id: int
    name: str
    code: str
    type: str
    precincts_count: int


class PublicPrecinctInfo(BaseModel):
    id: int
    precinct_number: int
    address: Optional[str]
    region_id: int
    region_name: str


class PublicResultsSummary(BaseModel):
    election_id: int
    total_votes: int
    total_precincts: int
    processed_precincts: int
    coverage_percent: float
    results: List[dict]


class PublicPrecinctResults(BaseModel):
    precinct_id: int
    precinct_number: int
    total_votes: int
    results: List[dict]


class PublicIncidentInfo(BaseModel):
    id: int
    precinct_id: int
    incident_type: str
    severity: str
    status: str
    created_at: str


# === PUBLIC ENDPOINTS ===

@router.get("/elections", response_model=List[PublicElectionInfo])
@limiter.limit("100/minute")
async def get_public_elections(request: Request, db: Session = Depends(get_db)):
    """
    Список выборов
    
    **Rate limit**: 100 requests/minute
    """
    elections = db.query(Election).all()
    
    return [
        PublicElectionInfo(
            id=e.id,
            name=e.name,
            election_date=e.election_date.isoformat() if e.election_date else None,
            election_type=e.election_type
        )
        for e in elections
    ]


@router.get("/elections/{election_id}/summary", response_model=PublicResultsSummary)
@limiter.limit("50/minute")
async def get_public_election_summary(
    request: Request,
    election_id: int,
    db: Session = Depends(get_db)
):
    """
    Общая сводка по выборам
    
    **Rate limit**: 50 requests/minute
    """
    # Проверка существования выборов
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    # Подсчёт голосов
    total_votes = db.query(func.sum(PrecinctResult.votes)).filter(
        PrecinctResult.election_id == election_id
    ).scalar() or 0
    
    # Участки
    total_precincts = db.query(func.count(Precinct.id)).scalar() or 0
    processed_precincts = db.query(
        func.count(func.distinct(PrecinctResult.precinct_id))
    ).filter(
        PrecinctResult.election_id == election_id
    ).scalar() or 0
    
    coverage = (processed_precincts / total_precincts * 100) if total_precincts > 0 else 0
    
    # Результаты по субъектам выборов
    subjects = db.query(ElectionSubject).filter(
        ElectionSubject.election_id == election_id
    ).all()
    
    results = []
    for subject in subjects:
        # Подсчёт через PrecinctResult
        votes = db.query(func.sum(PrecinctResult.votes)).filter(
            PrecinctResult.election_id == election_id,
            PrecinctResult.subject_id == subject.id
        ).scalar() or 0
        
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        
        results.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "subject_type": subject.subject_type,
            "ballot_number": subject.ballot_number,
            "votes": votes,
            "percentage": round(percentage, 2)
        })
    
    # Сортировка по голосам
    results.sort(key=lambda x: x["votes"], reverse=True)
    
    return PublicResultsSummary(
        election_id=election_id,
        total_votes=total_votes,
        total_precincts=total_precincts,
        processed_precincts=processed_precincts,
        coverage_percent=round(coverage, 2),
        results=results
    )


@router.get("/regions", response_model=List[PublicRegionInfo])
@limiter.limit("100/minute")
async def get_public_regions(
    request: Request,
    type_filter: Optional[str] = Query(None, description="Filter by type (e.g., 'oblast', 'rayon')"),
    db: Session = Depends(get_db)
):
    """
    Список регионов
    
    **Rate limit**: 100 requests/minute
    """
    query = db.query(Region)
    
    if type_filter:
        query = query.filter(Region.type == type_filter)
    
    regions = query.all()
    
    result = []
    for region in regions:
        precincts_count = db.query(func.count(Precinct.id)).filter(
            Precinct.region_id == region.id
        ).scalar() or 0
        
        result.append(PublicRegionInfo(
            id=region.id,
            name=region.name,
            code=region.code or "",
            type=region.type,
            precincts_count=precincts_count
        ))
    
    return result


@router.get("/precincts", response_model=List[PublicPrecinctInfo])
@limiter.limit("50/minute")
async def get_public_precincts(
    request: Request,
    region_id: Optional[int] = Query(None, description="Filter by region"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Список участков
    
    **Rate limit**: 50 requests/minute
    **Max limit**: 500 per request
    """
    query = db.query(Precinct)
    
    if region_id:
        query = query.filter(Precinct.region_id == region_id)
    
    precincts = query.offset(skip).limit(limit).all()
    
    result = []
    for precinct in precincts:
        region = db.query(Region).filter(Region.id == precinct.region_id).first()
        
        result.append(PublicPrecinctInfo(
            id=precinct.id,
            precinct_number=precinct.precinct_number,
            address=precinct.address,
            region_id=precinct.region_id,
            region_name=region.name if region else "Unknown"
        ))
    
    return result


@router.get("/precincts/{precinct_id}/results", response_model=PublicPrecinctResults)
@limiter.limit("100/minute")
async def get_public_precinct_results(
    request: Request,
    precinct_id: int,
    election_id: int = Query(..., description="Election ID"),
    db: Session = Depends(get_db)
):
    """
    Результаты по участку
    
    **Rate limit**: 100 requests/minute
    """
    # Проверка существования участка
    precinct = db.query(Precinct).filter(Precinct.id == precinct_id).first()
    if not precinct:
        raise HTTPException(status_code=404, detail="Precinct not found")
    
    # Получить результаты через PrecinctResult
    precinct_results = db.query(PrecinctResult).filter(
        PrecinctResult.precinct_id == precinct_id,
        PrecinctResult.election_id == election_id
    ).all()
    
    if not precinct_results:
        raise HTTPException(status_code=404, detail="No results for this precinct")
    
    total_votes = sum(pr.votes for pr in precinct_results)
    
    results = []
    for pr in precinct_results:
        subject = db.query(ElectionSubject).filter(
            ElectionSubject.id == pr.subject_id
        ).first()
        
        percentage = (pr.votes / total_votes * 100) if total_votes > 0 else 0
        
        results.append({
            "subject_id": pr.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "votes": pr.votes,
            "percentage": round(percentage, 2)
        })
    
    # Сортировка по голосам
    results.sort(key=lambda x: x["votes"], reverse=True)
    
    return PublicPrecinctResults(
        precinct_id=precinct_id,
        precinct_number=precinct.precinct_number,
        total_votes=total_votes,
        results=results
    )


@router.get("/incidents", response_model=List[PublicIncidentInfo])
@limiter.limit("50/minute")
async def get_public_incidents(
    request: Request,
    region_id: Optional[int] = Query(None, description="Filter by region"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Публичные инциденты (только RESOLVED)
    
    **Rate limit**: 50 requests/minute
    **Max limit**: 200 per request
    """
    query = db.query(Incident).filter(
        Incident.status == 'RESOLVED'  # Только разрешённые
    )
    
    if region_id:
        # Фильтр по региону через precinct
        query = query.join(Precinct).filter(
            Precinct.region_id == region_id
        )
    
    if severity:
        query = query.filter(Incident.severity == severity)
    
    incidents = query.order_by(
        Incident.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return [
        PublicIncidentInfo(
            id=incident.id,
            precinct_id=incident.precinct_id,
            incident_type=incident.type.value if hasattr(incident.type, 'value') else str(incident.type),
            severity=incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity),
            status=incident.status.value if hasattr(incident.status, 'value') else str(incident.status),
            created_at=incident.created_at.isoformat()
        )
        for incident in incidents
    ]


@router.get("/stats/observers")
@limiter.limit("30/minute")
async def get_public_observer_stats(request: Request, db: Session = Depends(get_db)):
    """
    Статистика наблюдателей (агрегированная)
    
    **Rate limit**: 30 requests/minute
    """
    total = db.query(func.count(ObserverProfile.id)).scalar() or 0
    verified = db.query(func.count(ObserverProfile.id)).filter(
        ObserverProfile.status == 'VERIFIED'
    ).scalar() or 0
    
    return {
        "total_observers": total,
        "verified_observers": verified,
        "verification_rate": round((verified / total * 100) if total > 0 else 0, 2)
    }


@router.get("/stats/protocols")
@limiter.limit("30/minute")
async def get_public_protocol_stats(request: Request, db: Session = Depends(get_db)):
    """
    Статистика протоколов
    
    **Rate limit**: 30 requests/minute
    """
    total = db.query(func.count(Protocol.id)).scalar() or 0
    verified = db.query(func.count(Protocol.id)).filter(
        Protocol.status == 'VERIFIED'
    ).scalar() or 0
    under_review = db.query(func.count(Protocol.id)).filter(
        Protocol.status == 'UNDER_REVIEW'
    ).scalar() or 0
    
    return {
        "total_protocols": total,
        "verified_protocols": verified,
        "under_review_protocols": under_review,
        "verification_rate": round((verified / total * 100) if total > 0 else 0, 2)
    }


@router.get("/rate-limit-info")
async def get_rate_limit_info(request: Request) -> dict:
    """
    Информация о rate limits
    
    **No rate limit** on this endpoint
    """
    return {
        "rate_limits": {
            "/api/public/elections": "100 requests/minute",
            "/api/public/elections/{id}/summary": "50 requests/minute",
            "/api/public/regions": "100 requests/minute",
            "/api/public/precincts": "50 requests/minute",
            "/api/public/precincts/{id}/results": "100 requests/minute",
            "/api/public/incidents": "50 requests/minute",
            "/api/public/stats/*": "30 requests/minute"
        },
        "notes": [
            "Rate limits are per IP address",
            "Exceeding limits returns HTTP 429",
            "Limits reset every minute"
        ]
    }


@router.get("/health")
async def public_api_health() -> dict:
    """
    Health check для public API
    
    **No rate limit** on this endpoint
    """
    return {
        "status": "healthy",
        "api_version": "1.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# === BOUNDARIES / GeoJSON API ===

import json
from pathlib import Path
from fastapi.responses import JSONResponse

BOUNDARIES_DIR = Path(__file__).parent.parent / "data" / "boundaries"


@router.get("/boundaries/precincts")
@limiter.limit("30/minute")
async def get_precincts_geojson(
    request: Request,
    city: Optional[str] = Query(None, description="Фильтр по городу (например, 'Усть-Каменогорск')"),
    precinct_id: Optional[int] = Query(None, description="Фильтр по номеру участка")
):
    """
    GeoJSON с границами избирательных участков.
    
    Возвращает FeatureCollection с полигонами участков для отображения на карте Leaflet.
    
    **Rate limit**: 30 requests/minute
    
    **Пример использования в Leaflet:**
    ```javascript
    fetch('/api/public/boundaries/precincts')
        .then(r => r.json())
        .then(geojson => L.geoJSON(geojson).addTo(map));
    ```
    """
    geojson_file = BOUNDARIES_DIR / "ust_kamenogorsk_precincts.geojson"
    
    if not geojson_file.exists():
        raise HTTPException(
            status_code=404, 
            detail="GeoJSON file not found. Run boundary pipeline first."
        )
    
    with open(geojson_file, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    
    # Фильтрация
    if city or precinct_id:
        filtered_features = []
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            
            if city and city.lower() not in props.get("city", "").lower():
                continue
            if precinct_id and props.get("precinct_id") != precinct_id:
                continue
            
            filtered_features.append(feature)
        
        geojson["features"] = filtered_features
    
    return JSONResponse(content=geojson)


@router.get("/boundaries/precincts/{precinct_id}")
@limiter.limit("100/minute")
async def get_precinct_boundary(
    request: Request,
    precinct_id: int,
    city: Optional[str] = Query(None, description="Фильтр по городу для устранения неоднозначности")
):
    """
    GeoJSON с границей одного участка.
    
    **Rate limit**: 100 requests/minute
    """
    geojson_file = BOUNDARIES_DIR / "ust_kamenogorsk_precincts.geojson"
    
    if not geojson_file.exists():
        raise HTTPException(status_code=404, detail="GeoJSON file not found")
    
    with open(geojson_file, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    
    matches = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        if props.get("precinct_id") != precinct_id:
            continue
        if city and city.lower() not in props.get("city", "").lower():
            continue
        matches.append(feature)

    if not matches:
        raise HTTPException(status_code=404, detail=f"Precinct {precinct_id} not found")

    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Multiple precincts found with same precinct_id. Provide ?city=... or use /api/public/boundaries/precincts with filters.",
        )

    return JSONResponse(content=matches[0])


@router.get("/boundaries/stats")
@limiter.limit("30/minute")
async def get_boundaries_stats(request: Request):
    """
    Статистика по границам участков.
    
    **Rate limit**: 30 requests/minute
    """
    geojson_file = BOUNDARIES_DIR / "ust_kamenogorsk_precincts.geojson"
    
    if not geojson_file.exists():
        return {
            "status": "not_generated",
            "message": "Run python scripts/full_boundary_pipeline.py to generate boundaries"
        }
    
    with open(geojson_file, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    
    features = geojson.get("features", [])
    
    # Статистика
    cities = {}
    polygon_sources = {}
    
    for feature in features:
        props = feature.get("properties", {})
        
        city = props.get("city", "Unknown")
        cities[city] = cities.get(city, 0) + 1
        
        source = props.get("polygon_source", "unknown")
        polygon_sources[source] = polygon_sources.get(source, 0) + 1
    
    return {
        "status": "ready",
        "total_precincts": len(features),
        "cities": cities,
        "polygon_sources": polygon_sources,
        "file_size_bytes": geojson_file.stat().st_size
    }

