from fastapi import FastAPI, Form, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal, engine
from app import models
# Import extended models to ensure they are registered with Base
from app import models_extended

# Импорт роутов
from app.routes_auth import router as auth_router
from app.routes_observers import router as observers_router
from app.routes_protocols import router as protocols_router
from app.routes_results import router as results_router
from app.routes_audit import router as audit_router
from app.routes_fraud import router as fraud_router
from app.routes_media import router as media_router
from app.routes_websocket import router as websocket_router
from app.routes_public import router as public_router, limiter
from app.routes_crisis import router as crisis_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Импорт middleware для аудита
from app.audit import audit_middleware

# Создать таблицы
Base = models.Base
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RK Elections Open Results API", version="1.0.0")


@app.get("/health")
async def health() -> dict:
    """Lightweight health endpoint for process readiness.

    Intentionally does not touch the database so startup probes can succeed
    even if Postgres is still coming up.
    """
    return {"status": "ok"}

# Rate limiter для public API
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Подключить роуты
app.include_router(auth_router)
app.include_router(observers_router)
app.include_router(protocols_router)
app.include_router(results_router)
app.include_router(audit_router)
app.include_router(fraud_router)
app.include_router(media_router)
app.include_router(websocket_router)
app.include_router(public_router)
app.include_router(crisis_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit middleware
app.middleware("http")(audit_middleware)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _known_party_names(db: Session) -> set[str]:
    names = db.query(models.ElectionSubject.name).filter(
        models.ElectionSubject.subject_type == "party",
    ).all()
    normalized: set[str] = set()
    for row in names:
        if not row:
            continue
        name = (row[0] or "").strip()
        if not name:
            continue
        if name.casefold() in {"против всех", "against all"}:
            continue
        normalized.add(name.casefold())
    return normalized


def _normalize_subject_type(
    *,
    election: "models.Election | None",
    subject: "models.ElectionSubject",
    known_party_names: set[str],
) -> str:
    raw = (subject.subject_type or "").strip().lower() or "candidate"

    # Keep the stored type for the special "against all" option.
    if (subject.name or "").strip().lower() in {"против всех", "against all"}:
        return raw

    # Data may be seeded via legacy pipelines where parties were inserted as candidates.
    # For presidential elections, reclassify any subject whose name matches known parties.
    if election and (election.election_type or "").strip().lower() == "presidential":
        if (subject.name or "").strip().casefold() in known_party_names:
            return "party"

    return raw


def _collect_descendant_region_ids(db: Session, root_region_id: int) -> list[int]:
    """Return root + all descendants (BFS) using regions.parent_id."""
    seen: set[int] = set()
    queue: list[int] = [root_region_id]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        children = db.query(models.Region.id).filter(models.Region.parent_id == current).all()
        for row in children:
            child_id = int(row[0])
            if child_id not in seen:
                queue.append(child_id)
    return list(seen)


@app.get("/api/elections/{election_id}/summary", response_class=JSONResponse)
async def get_election_summary(election_id: int, region_id: int | None = None):
    """Unified summary for UI: country-wide or within a region subtree.

    Uses `precinct_results` + `election_subjects`, so it works for both candidates and parties.
    Frontend can split by `subject_type` (candidate/party).
    """
    db = SessionLocal()
    try:
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        known_party_names = _known_party_names(db)

        precinct_query = db.query(models.Precinct.id)
        scope: str = "country"
        region_name: str | None = None
        if region_id is not None:
            scope = "region"
            region = db.query(models.Region).filter(models.Region.id == region_id).first()
            if not region:
                raise HTTPException(status_code=404, detail="Region not found")
            region_name = region.name

            region_ids = _collect_descendant_region_ids(db, region_id)
            precinct_query = precinct_query.filter(models.Precinct.region_id.in_(region_ids))

        precinct_ids_subq = precinct_query.subquery()

        total_precincts = db.query(func.count(models.Precinct.id))
        if region_id is not None:
            total_precincts = total_precincts.filter(models.Precinct.id.in_(precinct_ids_subq))
        total_precincts_val = int(total_precincts.scalar() or 0)

        processed_precincts = db.query(func.count(func.distinct(models.PrecinctResult.precinct_id))).filter(
            models.PrecinctResult.election_id == election_id
        )
        if region_id is not None:
            processed_precincts = processed_precincts.filter(models.PrecinctResult.precinct_id.in_(precinct_ids_subq))
        processed_precincts_val = int(processed_precincts.scalar() or 0)

        votes_sum_q = db.query(func.coalesce(func.sum(models.PrecinctResult.votes), 0)).filter(
            models.PrecinctResult.election_id == election_id
        )
        if region_id is not None:
            votes_sum_q = votes_sum_q.filter(models.PrecinctResult.precinct_id.in_(precinct_ids_subq))
        total_votes_val = int(votes_sum_q.scalar() or 0)

        rows = db.query(
            models.PrecinctResult.subject_id,
            func.coalesce(func.sum(models.PrecinctResult.votes), 0).label("votes"),
        ).filter(
            models.PrecinctResult.election_id == election_id
        )
        if region_id is not None:
            rows = rows.filter(models.PrecinctResult.precinct_id.in_(precinct_ids_subq))

        rows = rows.group_by(models.PrecinctResult.subject_id).all()

        results: list[dict] = []
        for subject_id, votes in rows:
            subject = db.query(models.ElectionSubject).filter(models.ElectionSubject.id == subject_id).first()
            if not subject:
                continue
            pct = (int(votes) / total_votes_val * 100) if total_votes_val > 0 else 0
            results.append(
                {
                    "subject_id": int(subject.id),
                    "subject_name": subject.name,
                    "subject_type": _normalize_subject_type(
                        election=election,
                        subject=subject,
                        known_party_names=known_party_names,
                    ),
                    "votes": int(votes),
                    "percentage": round(pct, 2),
                }
            )

        results.sort(key=lambda x: x["votes"], reverse=True)

        coverage = (processed_precincts_val / total_precincts_val * 100) if total_precincts_val > 0 else 0

        payload = {
            "election_id": election_id,
            "scope": scope,
            "region_id": region_id,
            "region_name": region_name,
            "total_votes": total_votes_val,
            "total_precincts": total_precincts_val,
            "processed_precincts": processed_precincts_val,
            "coverage_percent": round(coverage, 2),
            "results": results,
        }
        return JSONResponse(content=payload, media_type="application/json; charset=utf-8")
    finally:
        db.close()

@app.get("/api/elections", response_class=JSONResponse)
async def get_elections():
    db = SessionLocal()
    try:
        elections = db.query(models.Election).all()
        result = [
            {
                "id": e.id,
                "name": e.name,
                "election_date": e.election_date.isoformat() if e.election_date else None,
                "election_type": e.election_type,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in elections
        ]
        return JSONResponse(content=result, media_type="application/json; charset=utf-8")
    finally:
        db.close()

@app.get("/api/elections/{election_id}")
async def get_election(election_id: int):
    db = SessionLocal()
    try:
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        return {
            "id": election.id,
            "name": election.name,
            "election_date": election.election_date.isoformat() if election.election_date else None,
            "election_type": election.election_type,
            "created_at": election.created_at.isoformat() if election.created_at else None
        }
    finally:
        db.close()

@app.get("/api/elections/{election_id}/regions", response_class=JSONResponse)
async def get_regions(election_id: int):
    db = SessionLocal()
    try:
        regions = db.query(models.Region).filter(
            models.Region.parent_id.is_(None)
        ).all()
        
        result = []
        for r in regions:
            result.append({
                "id": r.id,
                "name": r.name,
                "code": r.code if r.code else "",
                "region_type": r.type if r.type else "REGION"
            })
        
        return JSONResponse(content=result)
    except Exception as e:
        import traceback
        print("=" * 80)
        print("ERROR in get_regions:")
        print(str(e))
        traceback.print_exc()
        print("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/regions/{region_id}/children")
async def get_child_regions(region_id: int):
    db = SessionLocal()
    try:
        children = db.query(models.Region).filter(
            models.Region.parent_id == region_id
        ).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "type": c.type,
                "parent_id": c.parent_id
            }
            for c in children
        ]
    finally:
        db.close()

@app.get("/api/regions/{region_id}/precincts")
async def get_precincts(region_id: int):
    db = SessionLocal()
    try:
        precincts = db.query(models.Precinct).filter(
            models.Precinct.region_id == region_id
        ).all()
        return [
            {
                "id": p.id,
                "number": p.precinct_number,
                "name": f"Участок №{p.precinct_number}",
                "address": p.address if p.address else "",
                "region_id": p.region_id
            }
            for p in precincts
        ]
    finally:
        db.close()

@app.get("/api/precincts/{precinct_id}/results/{election_id}")
async def get_precinct_results(precinct_id: int, election_id: int):
    db = SessionLocal()
    try:
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        known_party_names = _known_party_names(db)
        results = db.query(models.PrecinctResult).filter(
            models.PrecinctResult.precinct_id == precinct_id,
            models.PrecinctResult.election_id == election_id
        ).all()
        
        subjects = []
        for r in results:
            subject = db.query(models.ElectionSubject).filter(
                models.ElectionSubject.id == r.subject_id
            ).first()
            if subject:
                subjects.append({
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "subject_type": _normalize_subject_type(
                        election=election,
                        subject=subject,
                        known_party_names=known_party_names,
                    ),
                    "votes": r.votes,
                    "percentage": r.percentage
                })
        
        return {"precinct_id": precinct_id, "election_id": election_id, "results": subjects}
    finally:
        db.close()

@app.get("/api/elections/{election_id}/precinct/{precinct_id}")
async def get_precinct_details(election_id: int, precinct_id: int):
    """Получить детальную информацию об участке для конкретных выборов"""
    db = SessionLocal()
    try:
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        known_party_names = _known_party_names(db)
        # Получить участок
        precinct = db.query(models.Precinct).filter(
            models.Precinct.id == precinct_id
        ).first()
        
        if not precinct:
            # Создать участок если не существует
            precinct = models.Precinct(
                id=precinct_id,
                region_id=1,  # Default region
                precinct_number=precinct_id,
                address=f"Участок {precinct_id}",
                voters_registered=1000
            )
            db.add(precinct)
            db.commit()
        
        # Получить регион
        region = db.query(models.Region).filter(
            models.Region.id == precinct.region_id
        ).first()
        
        region_path = region.name if region else "Не указано"
        
        # Получить результаты
        results = db.query(models.PrecinctResult).filter(
            models.PrecinctResult.precinct_id == precinct_id,
            models.PrecinctResult.election_id == election_id
        ).all()
        
        subjects = []
        for r in results:
            subject = db.query(models.ElectionSubject).filter(
                models.ElectionSubject.id == r.subject_id
            ).first()
            if subject:
                subjects.append({
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "subject_type": _normalize_subject_type(
                        election=election,
                        subject=subject,
                        known_party_names=known_party_names,
                    ),
                    "votes": r.votes
                })
        
        # Получить фото протоколов
        photos = db.query(models.ProtocolPhoto).filter(
            models.ProtocolPhoto.precinct_id == precinct_id,
            models.ProtocolPhoto.election_id == election_id
        ).all()
        
        protocol_photos = [p.image_url for p in photos]
        
        return {
            "precinct_id": precinct_id,
            "precinct_number": precinct.precinct_number,
            "region_path": region_path,
            "subjects": subjects,
            "protocol_photos": protocol_photos
        }
    finally:
        db.close()

@app.post("/api/protocol/upload")
async def upload_protocol(
    election_id: int = Form(...),
    precinct_id: int = Form(...),
    file: UploadFile = File(...)
):
    import os
    import uuid
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Проверить выборы и участок
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        
        precinct = db.query(models.Precinct).filter(models.Precinct.id == precinct_id).first()
        if not precinct:
            raise HTTPException(status_code=404, detail="Precinct not found")
        
        # Сохранить файл
        upload_dir = "uploads/protocols"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Записать в БД
        protocol_photo = models.ProtocolPhoto(
            election_id=election_id,
            precinct_id=precinct_id,
            image_url=file_path,
            uploaded_at=datetime.utcnow()
        )
        db.add(protocol_photo)
        db.commit()
        
        return {"message": "Протокол успешно загружен", "file_id": protocol_photo.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/results/upload-csv")
async def upload_results_csv(
    election_id: int = Form(...),
    file: UploadFile = File(...)
):
    """Загрузка результатов из CSV файла
    
    Формат CSV:
    precinct_number,candidate_name,votes
    101,Касым-Жомарт Токаев,1250
    101,Марат Нурланов,980
    """
    import csv
    import io
    
    db = SessionLocal()
    try:
        # Проверить выборы
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        
        # Читать CSV
        content = await file.read()
        csv_text = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        added_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                precinct_number = int(row['precinct_number'])
                candidate_name = row['candidate_name'].strip()
                votes = int(row['votes'])
                
                # Найти участок
                precinct = db.query(models.Precinct).filter(
                    models.Precinct.precinct_number == precinct_number
                ).first()
                
                if not precinct:
                    errors.append(f"Строка {row_num}: участок №{precinct_number} не найден")
                    continue
                
                # Найти кандидата
                subject = db.query(models.ElectionSubject).filter(
                    models.ElectionSubject.election_id == election_id,
                    models.ElectionSubject.name == candidate_name
                ).first()
                
                if not subject:
                    errors.append(f"Строка {row_num}: кандидат '{candidate_name}' не найден")
                    continue
                
                # Проверить существование записи
                existing = db.query(models.PrecinctResult).filter(
                    models.PrecinctResult.election_id == election_id,
                    models.PrecinctResult.precinct_id == precinct.id,
                    models.PrecinctResult.subject_id == subject.id
                ).first()
                
                if existing:
                    # Обновить
                    existing.votes = votes
                else:
                    # Создать новую запись
                    result = models.PrecinctResult(
                        election_id=election_id,
                        precinct_id=precinct.id,
                        subject_id=subject.id,
                        votes=votes
                    )
                    db.add(result)
                
                added_count += 1
                
            except Exception as e:
                errors.append(f"Строка {row_num}: {str(e)}")
        
        db.commit()
        
        return {
            "message": f"Загружено {added_count} результатов",
            "added": added_count,
            "errors": errors
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/elections/{election_id}/subjects")
async def get_election_subjects(election_id: int):
    db = SessionLocal()
    try:
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        known_party_names = _known_party_names(db)
        subjects = db.query(models.ElectionSubject).filter(
            models.ElectionSubject.election_id == election_id
        ).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "subject_type": _normalize_subject_type(
                    election=election,
                    subject=s,
                    known_party_names=known_party_names,
                ),
                "ballot_number": getattr(s, 'ballot_number', None)
            }
            for s in subjects
        ]
    finally:
        db.close()

# === ANALYTICS ENDPOINTS ===

@app.get("/api/analytics/elections/{election_id}/summary")
async def get_election_summary(election_id: int):
    """Общая статистика по выборам"""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        known_party_names = _known_party_names(db)
        
        # Получить всех кандидатов
        subjects = db.query(models.ElectionSubject).filter(
            models.ElectionSubject.election_id == election_id
        ).all()
        
        # Подсчитать голоса для каждого кандидата
        results_summary = []
        total_votes = 0
        
        for subject in subjects:
            votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
                models.PrecinctResult.election_id == election_id,
                models.PrecinctResult.subject_id == subject.id
            ).scalar() or 0
            
            total_votes += votes
            results_summary.append({
                "subject_id": subject.id,
                "name": subject.name,
                "subject_type": _normalize_subject_type(
                    election=election,
                    subject=subject,
                    known_party_names=known_party_names,
                ),
                "votes": votes
            })
        
        # Рассчитать проценты
        for result in results_summary:
            result["percentage"] = round((result["votes"] / total_votes * 100) if total_votes > 0 else 0, 2)
        
        # Сортировать по количеству голосов
        results_summary.sort(key=lambda x: x["votes"], reverse=True)
        
        # Подсчитать количество участков
        total_precincts = db.query(func.count(models.Precinct.id)).scalar()
        processed_precincts = db.query(func.count(func.distinct(models.PrecinctResult.precinct_id))).filter(
            models.PrecinctResult.election_id == election_id
        ).scalar()
        
        return {
            "election_id": election_id,
            "total_votes": total_votes,
            "total_precincts": total_precincts,
            "processed_precincts": processed_precincts,
            "results": results_summary
        }
    finally:
        db.close()

@app.get("/api/elections/{election_id}/stats")
async def get_election_stats(election_id: int):
    """Статистика по выборам для фронтенда"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Подсчет голосов
        total_votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
            models.PrecinctResult.election_id == election_id
        ).scalar() or 0
        
        # Участки
        total_precincts = db.query(func.count(models.Precinct.id)).scalar() or 0
        precincts_with_results = db.query(func.count(func.distinct(models.PrecinctResult.precinct_id))).filter(
            models.PrecinctResult.election_id == election_id
        ).scalar() or 0
        
        # Протоколы
        total_protocols = db.query(func.count(models.ProtocolPhoto.id)).filter(
            models.ProtocolPhoto.election_id == election_id
        ).scalar() or 0
        
        coverage_percent = round((precincts_with_results / total_precincts * 100) if total_precincts > 0 else 0, 2)
        
        return {
            "total_votes": total_votes,
            "total_precincts": total_precincts,
            "precincts_with_results": precincts_with_results,
            "coverage_percent": coverage_percent,
            "total_protocols": total_protocols
        }
    finally:
        db.close()

@app.get("/api/precincts/{precinct_id}/results/{election_id}")
async def get_precinct_results(
    precinct_id: int,
    election_id: int,
    db: Session = Depends(get_db)
):
    """Получить результаты по конкретному участку"""
    election = db.query(models.Election).filter(models.Election.id == election_id).first()
    known_party_names = _known_party_names(db)
    results = db.query(
        models.PrecinctResult,
        models.ElectionSubject
    ).join(
        models.ElectionSubject,
        models.PrecinctResult.subject_id == models.ElectionSubject.id
    ).filter(
        models.PrecinctResult.precinct_id == precinct_id,
        models.PrecinctResult.election_id == election_id
    ).all()
    
    total_votes = sum(r[0].votes for r in results)
    
    return {
        "precinct_id": precinct_id,
        "election_id": election_id,
        "total_votes": total_votes,
        "results": [
            {
                "subject_id": r[1].id,
                "subject_name": r[1].name,
                "subject_type": _normalize_subject_type(
                    election=election,
                    subject=r[1],
                    known_party_names=known_party_names,
                ),
                "votes": r[0].votes,
                "percentage": round((r[0].votes / total_votes * 100), 2) if total_votes > 0 else 0
            }
            for r in results
        ]
    }

@app.get("/api/elections/{election_id}/aggregate")
async def get_aggregated_results(election_id: int, level: str = "country"):
    """Агрегированные результаты по уровням"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Получить название выборов
        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        known_party_names = _known_party_names(db)
        
        rows = []
        
        if level == "country":
            # Результаты по всей стране
            subjects = db.query(models.ElectionSubject).filter(
                models.ElectionSubject.election_id == election_id
            ).all()
            
            for subject in subjects:
                votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
                    models.PrecinctResult.election_id == election_id,
                    models.PrecinctResult.subject_id == subject.id
                ).scalar() or 0
                
                rows.append({
                    "level_name": "Республика Казахстан",
                    "subject_name": subject.name,
                    "subject_type": _normalize_subject_type(
                        election=election,
                        subject=subject,
                        known_party_names=known_party_names,
                    ),
                    "votes": votes
                })
        
        elif level == "region":
            # Результаты по областям
            regions = db.query(models.Region).filter(
                models.Region.parent_id == None
            ).all()
            
            for region in regions:
                subjects = db.query(models.ElectionSubject).filter(
                    models.ElectionSubject.election_id == election_id
                ).all()
                
                for subject in subjects:
                    # Подсчет голосов по региону через участки
                    votes = db.query(func.sum(models.PrecinctResult.votes)).join(
                        models.Precinct
                    ).filter(
                        models.PrecinctResult.election_id == election_id,
                        models.PrecinctResult.subject_id == subject.id,
                        models.Precinct.region_id == region.id
                    ).scalar() or 0
                    
                    if votes > 0:
                        rows.append({
                            "level_name": region.name,
                            "subject_name": subject.name,
                            "subject_type": _normalize_subject_type(
                                election=election,
                                subject=subject,
                                known_party_names=known_party_names,
                            ),
                            "votes": votes
                        })
        
        elif level in ["district", "local"]:
            # Для районов и локальных уровней
            region_type = "district" if level == "district" else "local"
            regions = db.query(models.Region).filter(
                models.Region.type == region_type
            ).all()
            
            for region in regions:
                subjects = db.query(models.ElectionSubject).filter(
                    models.ElectionSubject.election_id == election_id
                ).all()
                
                for subject in subjects:
                    votes = db.query(func.sum(models.PrecinctResult.votes)).join(
                        models.Precinct
                    ).filter(
                        models.PrecinctResult.election_id == election_id,
                        models.PrecinctResult.subject_id == subject.id,
                        models.Precinct.region_id == region.id
                    ).scalar() or 0
                    
                    if votes > 0:
                        rows.append({
                            "level_name": region.name,
                            "subject_name": subject.name,
                            "subject_type": _normalize_subject_type(
                                election=election,
                                subject=subject,
                                known_party_names=known_party_names,
                            ),
                            "votes": votes
                        })
        
        # Подсчитать общее количество голосов
        total_votes = sum(row["votes"] for row in rows)
        
        # Добавить проценты
        for row in rows:
            row["percentage"] = round((row["votes"] / total_votes * 100), 2) if total_votes > 0 else 0
        
        # Агрегировать по кандидатам для level=country
        if level == "country":
            aggregated = {}
            for row in rows:
                name = row["subject_name"]
                if name not in aggregated:
                    aggregated[name] = {
                        "subject_name": name,
                        "subject_type": row["subject_type"],
                        "votes": 0
                    }
                aggregated[name]["votes"] += row["votes"]
            
            results = list(aggregated.values())
            for r in results:
                r["percentage"] = round((r["votes"] / total_votes * 100), 2) if total_votes > 0 else 0
            
            return {
                "election_id": election_id,
                "election_name": election.name,
                "level": level,
                "total_votes": total_votes,
                "results": results
            }
        
        return {
            "election_id": election_id,
            "election_name": election.name,
            "level": level,
            "total_votes": total_votes,
            "rows": rows
        }
    finally:
        db.close()

@app.get("/api/analytics/elections/{election_id}/by_region")
async def get_results_by_region(election_id: int):
    """Результаты по регионам"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Получаем все регионы, где есть участки с результатами
        regions_with_data = db.query(models.Region).join(
            models.Precinct, models.Region.id == models.Precinct.region_id
        ).join(
            models.PrecinctResult, models.Precinct.id == models.PrecinctResult.precinct_id
        ).filter(
            models.PrecinctResult.election_id == election_id
        ).distinct().all()
        
        region_results = []
        
        for region in regions_with_data:
            # Получить участки региона
            precincts = db.query(models.Precinct).filter(
                models.Precinct.region_id == region.id
            ).all()
            
            precinct_ids = [p.id for p in precincts]
            
            if not precinct_ids:
                continue
            
            # Получить результаты по кандидатам
            candidate_results = {}
            total_votes = 0
            
            results = db.query(
                models.PrecinctResult.subject_id,
                func.sum(models.PrecinctResult.votes).label('total_votes')
            ).filter(
                models.PrecinctResult.election_id == election_id,
                models.PrecinctResult.precinct_id.in_(precinct_ids)
            ).group_by(models.PrecinctResult.subject_id).all()
            
            for result in results:
                subject = db.query(models.ElectionSubject).filter(
                    models.ElectionSubject.id == result.subject_id
                ).first()
                if subject:
                    candidate_results[subject.name] = result.total_votes
                    total_votes += result.total_votes
            
            # Найти победителя
            winner = max(candidate_results, key=candidate_results.get) if candidate_results else None
            
            region_results.append({
                "region_id": region.id,
                "region_name": region.name,
                "region_code": region.code,
                "total_votes": total_votes,
                "winner": winner,
                "winner_votes": candidate_results.get(winner, 0) if winner else 0,
                "results": candidate_results
            })
        
        return {"election_id": election_id, "regions": region_results}
    finally:
        db.close()

@app.get("/api/analytics/elections/{election_id}/comparison")
async def get_candidates_comparison(election_id: int):
    """Сравнительная таблица кандидатов"""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        election = db.query(models.Election).filter(models.Election.id == election_id).first()
        known_party_names = _known_party_names(db)
        
        subjects = db.query(models.ElectionSubject).filter(
            models.ElectionSubject.election_id == election_id
        ).all()
        
        comparison = []
        
        for subject in subjects:
            # Общие голоса
            total_votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
                models.PrecinctResult.election_id == election_id,
                models.PrecinctResult.subject_id == subject.id
            ).scalar() or 0
            
            # Количество участков, где победил (упрощенный подсчет)
            # Для каждого участка находим максимум голосов и проверяем, что это наш кандидат
            from sqlalchemy import and_
            subq = db.query(
                models.PrecinctResult.precinct_id,
                func.max(models.PrecinctResult.votes).label('max_votes')
            ).filter(
                models.PrecinctResult.election_id == election_id
            ).group_by(models.PrecinctResult.precinct_id).subquery()
            
            wins_count = db.query(func.count(models.PrecinctResult.precinct_id.distinct())).filter(
                models.PrecinctResult.election_id == election_id,
                models.PrecinctResult.subject_id == subject.id,
                models.PrecinctResult.precinct_id == subq.c.precinct_id,
                models.PrecinctResult.votes == subq.c.max_votes
            ).scalar() or 0
            
            # Средний процент (процент от общего числа голосов на всех участках)
            # Получаем общее число голосов на выборах
            all_votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
                models.PrecinctResult.election_id == election_id
            ).scalar() or 1  # Избегаем деления на ноль
            
            avg_percentage = round((total_votes / all_votes) * 100, 2) if all_votes > 0 else 0
            
            comparison.append({
                "subject_id": subject.id,
                "name": subject.name,
                "subject_type": _normalize_subject_type(
                    election=election,
                    subject=subject,
                    known_party_names=known_party_names,
                ),
                "total_votes": total_votes,
                "precincts_won": wins_count,
                "avg_percentage": round(float(avg_percentage), 2)
            })
        
        # Сортировать по голосам
        comparison.sort(key=lambda x: x["total_votes"], reverse=True)
        
        return {"election_id": election_id, "candidates": comparison}
    finally:
        db.close()

@app.get("/api/analytics/elections/{election_id}/charts")
async def get_charts_data(election_id: int):
    """Данные для графиков"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Данные для круговой диаграммы (распределение голосов)
        pie_data = []
        subjects = db.query(models.ElectionSubject).filter(
            models.ElectionSubject.election_id == election_id
        ).all()
        
        for subject in subjects:
            votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
                models.PrecinctResult.election_id == election_id,
                models.PrecinctResult.subject_id == subject.id
            ).scalar() or 0
            
            pie_data.append({
                "label": subject.name,
                "value": votes
            })
        
        # Данные для столбчатой диаграммы (голоса по регионам для топ-3 кандидатов)
        top_candidates = sorted(pie_data, key=lambda x: x["value"], reverse=True)[:3]
        
        regions = db.query(models.Region).filter(
            models.Region.parent_id.is_(None)
        ).limit(10).all()  # Топ-10 регионов
        
        bar_data = {
            "labels": [r.name for r in regions],
            "datasets": []
        }
        
        for candidate in top_candidates:
            subject = next((s for s in subjects if s.name == candidate["label"]), None)
            if not subject:
                continue
            
            region_votes = []
            for region in regions:
                precincts = db.query(models.Precinct).filter(
                    models.Precinct.region_id == region.id
                ).all()
                precinct_ids = [p.id for p in precincts]
                
                votes = db.query(func.sum(models.PrecinctResult.votes)).filter(
                    models.PrecinctResult.election_id == election_id,
                    models.PrecinctResult.subject_id == subject.id,
                    models.PrecinctResult.precinct_id.in_(precinct_ids)
                ).scalar() or 0
                
                region_votes.append(votes)
            
            bar_data["datasets"].append({
                "label": subject.name,
                "data": region_votes
            })
        
        return {
            "election_id": election_id,
            "pie_chart": pie_data,
            "bar_chart": bar_data
        }
    finally:
        db.close()


# Статические файлы (но не перехватываем API)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# HTML страницы фронтенда
@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

@app.get("/index.html")
async def serve_index_html():
    return FileResponse("frontend/index.html")

@app.get("/analytics.html")
async def serve_analytics():
    return FileResponse("frontend/analytics.html")

@app.get("/map.html")
async def serve_map():
    return FileResponse("frontend/map.html")

@app.get("/precinct.html")
async def serve_precinct():
    return FileResponse("frontend/precinct.html")

@app.get("/upload.html")
async def serve_upload():
    return FileResponse("frontend/upload.html")

@app.get("/coordinator.html")
async def serve_coordinator():
    return FileResponse("frontend/coordinator.html")

@app.get("/incidents.html")
async def serve_incidents():
    return FileResponse("frontend/incidents.html")

@app.get("/fraud.html")
async def serve_fraud():
    return FileResponse("frontend/fraud.html")

@app.get("/admin.html")
async def serve_admin():
    return FileResponse("frontend/admin.html")

@app.get("/login.html")
async def serve_login():
    return FileResponse("frontend/login.html")

@app.get("/realtime.html")
async def serve_realtime():
    return FileResponse("frontend/realtime.html")
