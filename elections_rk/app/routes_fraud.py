# API endpoints для anti-fraud detection (Task #9)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models_extended import User
from app.routes_auth import get_current_user, require_role
from app.fraud_detection import FraudDetector

router = APIRouter(prefix="/api/fraud", tags=["Fraud Detection"])


# Schemas
class FraudAlert(BaseModel):
    type: str
    severity: str
    details: dict


class RiskScoreResponse(BaseModel):
    observer_id: Optional[int] = None
    protocol_id: Optional[int] = None
    risk_score: int
    risk_level: str
    flags: List[str]


class ScanSummary(BaseModel):
    total_issues: int
    critical: int
    high: int
    medium: int
    low: int


class FullScanResponse(BaseModel):
    scan_timestamp: str
    duplicate_observers: List[dict]
    duplicate_protocols: List[dict]
    turnout_anomalies: List[dict]
    vote_share_anomalies: List[dict]
    timestamp_anomalies: List[dict]
    collusion_patterns: List[dict]
    geolocation_anomalies: List[dict]
    summary: ScanSummary


# Endpoints

@router.post("/scan/full", response_model=FullScanResponse)
def run_full_fraud_scan(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Запустить полное сканирование на мошенничество
    Только ADMIN и COORD
    
    Проверяет:
    - Дубликаты наблюдателей и протоколов
    - Аномалии явки и распределения голосов
    - Подозрительные временные паттерны
    - Паттерны сговора
    - Аномалии геолокации
    """
    detector = FraudDetector(db)
    results = detector.run_full_scan()
    return FullScanResponse(**results)


@router.get("/duplicates/observers")
def detect_duplicate_observers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить дубликаты наблюдателей
    (по ИИН, телефону, email)
    """
    detector = FraudDetector(db)
    duplicates = detector.detect_duplicate_observers()
    return {
        "duplicates": duplicates,
        "count": len(duplicates)
    }


@router.get("/duplicates/protocols")
def detect_duplicate_protocols(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить дублирующиеся протоколы
    (одинаковые file_hash для разных УИК)
    """
    detector = FraudDetector(db)
    duplicates = detector.detect_duplicate_protocols()
    return {
        "duplicates": duplicates,
        "count": len(duplicates)
    }


@router.get("/anomalies/turnout")
def detect_turnout_anomalies(
    threshold: float = Query(2.5, description="Количество стандартных отклонений"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить аномалии явки
    (УИК с явкой > threshold σ от среднего)
    """
    detector = FraudDetector(db)
    anomalies = detector.detect_turnout_anomalies(threshold)
    return {
        "anomalies": anomalies,
        "count": len(anomalies)
    }


@router.get("/anomalies/vote-share")
def detect_vote_share_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить аномалии распределения голосов
    (один кандидат >90%, ровные проценты)
    """
    detector = FraudDetector(db)
    anomalies = detector.detect_vote_share_anomalies()
    return {
        "anomalies": anomalies,
        "count": len(anomalies)
    }


@router.get("/anomalies/timestamps")
def detect_timestamp_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить временные аномалии
    (массовые загрузки, ранние загрузки)
    """
    detector = FraudDetector(db)
    anomalies = detector.detect_timestamp_anomalies()
    return {
        "anomalies": anomalies,
        "count": len(anomalies)
    }


@router.get("/anomalies/geolocation")
def detect_geolocation_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить аномалии геолокации
    (check-in далеко от УИК)
    """
    detector = FraudDetector(db)
    anomalies = detector.detect_geolocation_anomalies()
    return {
        "anomalies": anomalies,
        "count": len(anomalies)
    }


@router.get("/patterns/collusion")
def detect_collusion_patterns(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Обнаружить паттерны сговора
    (один наблюдатель загружает протоколы для многих УИК)
    """
    detector = FraudDetector(db)
    patterns = detector.detect_collusion_patterns()
    return {
        "patterns": patterns,
        "count": len(patterns)
    }


@router.get("/risk-score/observer/{observer_id}", response_model=RiskScoreResponse)
def get_observer_risk_score(
    observer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить risk score для наблюдателя
    
    Учитывает:
    - Статус верификации
    - Наличие обучения
    - Документы
    - Количество заявок
    - Неавторизованные загрузки протоколов
    """
    detector = FraudDetector(db)
    result = detector.calculate_observer_risk_score(observer_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return RiskScoreResponse(**result)


@router.get("/risk-score/protocol/{protocol_id}", response_model=RiskScoreResponse)
def get_protocol_risk_score(
    protocol_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить risk score для протокола
    
    Учитывает:
    - Наличие файла
    - Время загрузки
    - Наличие голосов
    - Аномальное количество голосов
    - Доминирующий кандидат
    """
    detector = FraudDetector(db)
    result = detector.calculate_protocol_risk_score(protocol_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return RiskScoreResponse(**result)


@router.get("/stats/summary")
def get_fraud_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Получить сводную статистику по мошенничеству
    Только ADMIN
    """
    detector = FraudDetector(db)
    
    # Быстрый подсчёт
    duplicate_observers_count = len(detector.detect_duplicate_observers())
    duplicate_protocols_count = len(detector.detect_duplicate_protocols())
    turnout_anomalies_count = len(detector.detect_turnout_anomalies())
    vote_anomalies_count = len(detector.detect_vote_share_anomalies())
    timestamp_anomalies_count = len(detector.detect_timestamp_anomalies())
    collusion_patterns_count = len(detector.detect_collusion_patterns())
    geo_anomalies_count = len(detector.detect_geolocation_anomalies())
    
    total_issues = (
        duplicate_observers_count +
        duplicate_protocols_count +
        turnout_anomalies_count +
        vote_anomalies_count +
        timestamp_anomalies_count +
        collusion_patterns_count +
        geo_anomalies_count
    )
    
    return {
        "total_issues": total_issues,
        "by_category": {
            "duplicate_observers": duplicate_observers_count,
            "duplicate_protocols": duplicate_protocols_count,
            "turnout_anomalies": turnout_anomalies_count,
            "vote_share_anomalies": vote_anomalies_count,
            "timestamp_anomalies": timestamp_anomalies_count,
            "collusion_patterns": collusion_patterns_count,
            "geolocation_anomalies": geo_anomalies_count
        }
    }


@router.get("/alerts/critical")
def get_critical_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить только критичные алерты
    """
    detector = FraudDetector(db)
    full_scan = detector.run_full_scan()
    
    critical_alerts = []
    
    # Собрать все алерты с severity=CRITICAL
    for category, items in full_scan.items():
        if category in ["scan_timestamp", "summary"]:
            continue
        
        for item in items:
            if item.get("severity") == "CRITICAL":
                critical_alerts.append({
                    "category": category,
                    **item
                })
    
    return {
        "critical_alerts": critical_alerts,
        "count": len(critical_alerts)
    }


@router.get("/alerts/high")
def get_high_priority_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить высокоприоритетные алерты (CRITICAL + HIGH)
    """
    detector = FraudDetector(db)
    full_scan = detector.run_full_scan()
    
    high_priority_alerts = []
    
    # Собрать алерты с severity=CRITICAL или HIGH
    for category, items in full_scan.items():
        if category in ["scan_timestamp", "summary"]:
            continue
        
        for item in items:
            severity = item.get("severity", "LOW")
            if severity in ["CRITICAL", "HIGH"]:
                high_priority_alerts.append({
                    "category": category,
                    **item
                })
    
    return {
        "high_priority_alerts": high_priority_alerts,
        "count": len(high_priority_alerts)
    }


@router.post("/batch-risk-score/observers")
def batch_observer_risk_scores(
    observer_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить risk scores для нескольких наблюдателей
    Максимум 100 за раз
    """
    if len(observer_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 observer_ids allowed")
    
    detector = FraudDetector(db)
    results = []
    
    for observer_id in observer_ids:
        score = detector.calculate_observer_risk_score(observer_id)
        if "error" not in score:
            results.append(score)
    
    return {
        "risk_scores": results,
        "count": len(results)
    }


@router.post("/batch-risk-score/protocols")
def batch_protocol_risk_scores(
    protocol_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Получить risk scores для нескольких протоколов
    Максимум 100 за раз
    """
    if len(protocol_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 protocol_ids allowed")
    
    detector = FraudDetector(db)
    results = []
    
    for protocol_id in protocol_ids:
        score = detector.calculate_protocol_risk_score(protocol_id)
        if "error" not in score:
            results.append(score)
    
    return {
        "risk_scores": results,
        "count": len(results)
    }
