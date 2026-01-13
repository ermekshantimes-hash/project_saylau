# Anti-fraud detection module (Task #9)
# Обнаружение аномалий, дубликатов, подозрительных паттернов

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, distinct
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import hashlib
from collections import Counter

from app.models_extended import (
    ObserverProfile, ObserverApplication, ObserverCheckin,
    Protocol, ProtocolItem, PrecinctTally, Incident,
    User, Candidate
)
from app.models import Precinct, Region


class FraudDetector:
    """
    Класс для обнаружения мошенничества и аномалий
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.alerts = []
    
    # === DUPLICATE DETECTION ===
    
    def detect_duplicate_observers(self) -> List[Dict]:
        """
        Обнаружение дубликатов наблюдателей по ИИН, телефону, email
        """
        duplicates = []
        
        # Дубликаты по ИИН
        iin_dupes = self.db.query(
            ObserverProfile.iin,
            func.count(ObserverProfile.id).label('count')
        ).group_by(ObserverProfile.iin).having(
            func.count(ObserverProfile.id) > 1
        ).all()
        
        for iin, count in iin_dupes:
            profiles = self.db.query(ObserverProfile).filter(
                ObserverProfile.iin == iin
            ).all()
            
            duplicates.append({
                "type": "duplicate_iin",
                "iin": iin,
                "count": count,
                "profile_ids": [p.id for p in profiles],
                "severity": "HIGH"
            })
        
        # Дубликаты по телефону
        phone_dupes = self.db.query(
            User.phone,
            func.count(User.id).label('count')
        ).filter(
            User.role == 'OBSERVER'
        ).group_by(User.phone).having(
            func.count(User.id) > 1
        ).all()
        
        for phone, count in phone_dupes:
            users = self.db.query(User).filter(
                User.phone == phone,
                User.role == 'OBSERVER'
            ).all()
            
            duplicates.append({
                "type": "duplicate_phone",
                "phone": phone,
                "count": count,
                "user_ids": [u.id for u in users],
                "severity": "MEDIUM"
            })
        
        return duplicates
    
    def detect_duplicate_protocols(self) -> List[Dict]:
        """
        Обнаружение дублирующихся протоколов (одинаковые хеши файлов)
        """
        duplicates = []
        
        hash_dupes = self.db.query(
            Protocol.file_hash,
            func.count(Protocol.id).label('count')
        ).filter(
            Protocol.file_hash.isnot(None)
        ).group_by(Protocol.file_hash).having(
            func.count(Protocol.id) > 1
        ).all()
        
        for file_hash, count in hash_dupes:
            protocols = self.db.query(Protocol).filter(
                Protocol.file_hash == file_hash
            ).all()
            
            # Проверить что протоколы для разных УИК
            precinct_ids = [p.precinct_id for p in protocols]
            if len(set(precinct_ids)) > 1:
                duplicates.append({
                    "type": "duplicate_protocol_hash",
                    "file_hash": file_hash[:16],
                    "count": count,
                    "protocol_ids": [p.id for p in protocols],
                    "precinct_ids": precinct_ids,
                    "severity": "CRITICAL"
                })
        
        return duplicates
    
    # === ANOMALY DETECTION ===
    
    def detect_turnout_anomalies(self, threshold: float = 2.5) -> List[Dict]:
        """
        Обнаружение аномальной явки (> threshold std от среднего)
        """
        anomalies = []
        
        # Получить все протоколы с подсчётом голосов
        protocols = self.db.query(Protocol).filter(
            Protocol.status == 'VERIFIED'
        ).all()
        
        turnouts = []
        protocol_map = {}
        
        for protocol in protocols:
            # Подсчитать общее количество голосов
            total_votes = self.db.query(func.sum(ProtocolItem.votes)).filter(
                ProtocolItem.protocol_id == protocol.id
            ).scalar() or 0
            
            if total_votes > 0:
                turnouts.append(total_votes)
                protocol_map[protocol.id] = total_votes
        
        if len(turnouts) < 10:
            return []  # Недостаточно данных
        
        # Статистика
        import statistics
        mean_turnout = statistics.mean(turnouts)
        stdev_turnout = statistics.stdev(turnouts)
        
        upper_bound = mean_turnout + (threshold * stdev_turnout)
        lower_bound = max(0, mean_turnout - (threshold * stdev_turnout))
        
        # Найти аномалии
        for protocol_id, votes in protocol_map.items():
            if votes > upper_bound or votes < lower_bound:
                protocol = self.db.query(Protocol).filter(
                    Protocol.id == protocol_id
                ).first()
                
                z_score = (votes - mean_turnout) / stdev_turnout if stdev_turnout > 0 else 0
                
                anomalies.append({
                    "type": "turnout_anomaly",
                    "protocol_id": protocol_id,
                    "precinct_id": protocol.precinct_id,
                    "votes": votes,
                    "mean": round(mean_turnout, 2),
                    "z_score": round(z_score, 2),
                    "severity": "HIGH" if abs(z_score) > 3 else "MEDIUM"
                })
        
        return anomalies
    
    def detect_vote_share_anomalies(self) -> List[Dict]:
        """
        Обнаружение подозрительного распределения голосов
        (один кандидат получает >90% или ровно круглые проценты)
        """
        anomalies = []
        
        protocols = self.db.query(Protocol).filter(
            Protocol.status == 'VERIFIED'
        ).all()
        
        for protocol in protocols:
            items = self.db.query(ProtocolItem).filter(
                ProtocolItem.protocol_id == protocol.id
            ).all()
            
            if not items:
                continue
            
            total_votes = sum(item.votes for item in items)
            if total_votes == 0:
                continue
            
            # Проверка 1: Доминирующий кандидат (>90%)
            for item in items:
                percentage = (item.votes / total_votes) * 100
                if percentage > 90:
                    candidate = self.db.query(Candidate).filter(
                        Candidate.id == item.candidate_id
                    ).first()
                    
                    anomalies.append({
                        "type": "dominant_candidate",
                        "protocol_id": protocol.id,
                        "precinct_id": protocol.precinct_id,
                        "candidate_id": item.candidate_id,
                        "candidate_name": candidate.name if candidate else "Unknown",
                        "percentage": round(percentage, 2),
                        "votes": item.votes,
                        "total_votes": total_votes,
                        "severity": "HIGH"
                    })
            
            # Проверка 2: Ровные проценты (50.00%, 33.33%, etc.)
            for item in items:
                percentage = (item.votes / total_votes) * 100
                # Проверить кратность 5% или 10%
                if percentage > 10 and (percentage % 5 == 0 or percentage % 10 == 0):
                    # Дополнительная проверка: точное совпадение
                    decimal_part = percentage - int(percentage)
                    if abs(decimal_part) < 0.01:  # Почти ровное число
                        anomalies.append({
                            "type": "round_percentage",
                            "protocol_id": protocol.id,
                            "precinct_id": protocol.precinct_id,
                            "candidate_id": item.candidate_id,
                            "percentage": round(percentage, 2),
                            "severity": "LOW"
                        })
        
        return anomalies
    
    def detect_timestamp_anomalies(self) -> List[Dict]:
        """
        Обнаружение подозрительных временных паттернов
        (массовые загрузки в одно время, загрузка до открытия участка)
        """
        anomalies = []
        
        # Проверка 1: Массовые загрузки протоколов в одну минуту
        upload_times = self.db.query(
            func.date_trunc('minute', Protocol.created_at).label('minute'),
            func.count(Protocol.id).label('count')
        ).group_by(
            func.date_trunc('minute', Protocol.created_at)
        ).having(
            func.count(Protocol.id) > 10  # >10 протоколов за минуту
        ).all()
        
        for minute, count in upload_times:
            protocols = self.db.query(Protocol).filter(
                func.date_trunc('minute', Protocol.created_at) == minute
            ).all()
            
            anomalies.append({
                "type": "bulk_upload",
                "timestamp": minute.isoformat(),
                "count": count,
                "protocol_ids": [p.id for p in protocols],
                "severity": "MEDIUM"
            })
        
        # Проверка 2: Загрузка протоколов до окончания голосования (20:00)
        # Предполагаем что голосование заканчивается в 20:00
        from datetime import time
        early_protocols = self.db.query(Protocol).filter(
            func.extract('hour', Protocol.created_at) < 20
        ).all()
        
        for protocol in early_protocols:
            hour = protocol.created_at.hour
            if hour < 18:  # До 18:00 вообще подозрительно
                anomalies.append({
                    "type": "early_upload",
                    "protocol_id": protocol.id,
                    "precinct_id": protocol.precinct_id,
                    "upload_time": protocol.created_at.isoformat(),
                    "hour": hour,
                    "severity": "HIGH"
                })
        
        return anomalies
    
    # === PATTERN DETECTION ===
    
    def detect_collusion_patterns(self) -> List[Dict]:
        """
        Обнаружение паттернов сговора
        (один наблюдатель загружает протоколы для многих УИК)
        """
        patterns = []
        
        # Наблюдатели с >5 протоколами
        uploader_stats = self.db.query(
            Protocol.uploader_user_id,
            func.count(Protocol.id).label('count'),
            func.count(func.distinct(Protocol.precinct_id)).label('precinct_count')
        ).filter(
            Protocol.uploader_user_id.isnot(None)
        ).group_by(Protocol.uploader_user_id).all()
        
        for user_id, protocol_count, precinct_count in uploader_stats:
            if protocol_count > 5 and precinct_count > 3:
                user = self.db.query(User).filter(User.id == user_id).first()
                
                patterns.append({
                    "type": "multi_precinct_uploader",
                    "user_id": user_id,
                    "phone": user.phone if user else None,
                    "protocol_count": protocol_count,
                    "precinct_count": precinct_count,
                    "severity": "MEDIUM" if precinct_count < 10 else "HIGH"
                })
        
        return patterns
    
    def detect_geolocation_anomalies(self) -> List[Dict]:
        """
        Обнаружение аномалий геолокации
        (check-in далеко от УИК)
        """
        anomalies = []
        
        checkins = self.db.query(ObserverCheckin).filter(
            ObserverCheckin.latitude.isnot(None),
            ObserverCheckin.longitude.isnot(None)
        ).all()
        
        for checkin in checkins:
            precinct = self.db.query(Precinct).filter(
                Precinct.id == checkin.precinct_id
            ).first()
            
            if not precinct or not precinct.latitude or not precinct.longitude:
                continue
            
            # Вычислить расстояние (упрощённая формула)
            lat_diff = abs(checkin.latitude - precinct.latitude)
            lon_diff = abs(checkin.longitude - precinct.longitude)
            
            # Примерное расстояние в км (очень грубо)
            distance_km = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111
            
            # Если >5 км - подозрительно
            if distance_km > 5:
                anomalies.append({
                    "type": "geolocation_mismatch",
                    "checkin_id": checkin.id,
                    "observer_id": checkin.observer_id,
                    "precinct_id": checkin.precinct_id,
                    "distance_km": round(distance_km, 2),
                    "severity": "HIGH" if distance_km > 50 else "MEDIUM"
                })
        
        return anomalies
    
    # === RISK SCORING ===
    
    def calculate_observer_risk_score(self, observer_id: int) -> Dict:
        """
        Расчёт risk score для наблюдателя
        """
        profile = self.db.query(ObserverProfile).filter(
            ObserverProfile.id == observer_id
        ).first()
        
        if not profile:
            return {"error": "Observer not found"}
        
        score = 0
        flags = []
        
        # Проверка 1: Профиль не верифицирован
        if profile.status != 'VERIFIED':
            score += 20
            flags.append("unverified_profile")
        
        # Проверка 2: Нет обучения
        if not profile.training_completed:
            score += 15
            flags.append("no_training")
        
        # Проверка 3: Нет документов
        if not profile.photo_id_url or not profile.certificate_url:
            score += 10
            flags.append("missing_documents")
        
        # Проверка 4: Множественные заявки
        app_count = self.db.query(func.count(ObserverApplication.id)).filter(
            ObserverApplication.observer_id == observer_id
        ).scalar()
        
        if app_count > 5:
            score += 10
            flags.append("many_applications")
        
        # Проверка 5: Отменённые заявки
        cancelled_count = self.db.query(func.count(ObserverApplication.id)).filter(
            ObserverApplication.observer_id == observer_id,
            ObserverApplication.status == 'CANCELLED'
        ).scalar()
        
        if cancelled_count > 2:
            score += 15
            flags.append("cancelled_applications")
        
        # Проверка 6: Загрузка протоколов для чужих УИК
        protocols = self.db.query(Protocol).filter(
            Protocol.uploader_user_id == profile.user_id
        ).all()
        
        assigned_precincts = self.db.query(ObserverApplication.precinct_id).filter(
            ObserverApplication.observer_id == observer_id,
            ObserverApplication.status == 'ASSIGNED'
        ).all()
        
        assigned_ids = {p[0] for p in assigned_precincts}
        unauthorized_uploads = sum(
            1 for p in protocols if p.precinct_id not in assigned_ids
        )
        
        if unauthorized_uploads > 0:
            score += 25
            flags.append("unauthorized_uploads")
        
        # Оценка риска
        if score >= 50:
            risk_level = "HIGH"
        elif score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "observer_id": observer_id,
            "risk_score": score,
            "risk_level": risk_level,
            "flags": flags,
            "profile_status": profile.status.value if hasattr(profile.status, 'value') else str(profile.status)
        }
    
    def calculate_protocol_risk_score(self, protocol_id: int) -> Dict:
        """
        Расчёт risk score для протокола
        """
        protocol = self.db.query(Protocol).filter(
            Protocol.id == protocol_id
        ).first()
        
        if not protocol:
            return {"error": "Protocol not found"}
        
        score = 0
        flags = []
        
        # Проверка 1: Нет файла
        if not protocol.file_url:
            score += 30
            flags.append("no_file")
        
        # Проверка 2: Загружен слишком рано
        if protocol.created_at.hour < 18:
            score += 20
            flags.append("early_upload")
        
        # Проверка 3: Нет items (голосов)
        item_count = self.db.query(func.count(ProtocolItem.id)).filter(
            ProtocolItem.protocol_id == protocol_id
        ).scalar()
        
        if item_count == 0:
            score += 25
            flags.append("no_votes")
        
        # Проверка 4: Аномальные голоса
        total_votes = self.db.query(func.sum(ProtocolItem.votes)).filter(
            ProtocolItem.protocol_id == protocol_id
        ).scalar() or 0
        
        if total_votes > 5000:  # Слишком много для одного УИК
            score += 15
            flags.append("excessive_votes")
        
        # Проверка 5: Один кандидат >90%
        items = self.db.query(ProtocolItem).filter(
            ProtocolItem.protocol_id == protocol_id
        ).all()
        
        if items and total_votes > 0:
            max_votes = max(item.votes for item in items)
            if (max_votes / total_votes) > 0.9:
                score += 20
                flags.append("dominant_candidate")
        
        # Оценка риска
        if score >= 50:
            risk_level = "HIGH"
        elif score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "protocol_id": protocol_id,
            "precinct_id": protocol.precinct_id,
            "risk_score": score,
            "risk_level": risk_level,
            "flags": flags,
            "status": protocol.status.value if hasattr(protocol.status, 'value') else str(protocol.status)
        }
    
    # === COMPREHENSIVE SCAN ===
    
    def run_full_scan(self) -> Dict:
        """
        Запустить полное сканирование на мошенничество
        """
        results = {
            "scan_timestamp": datetime.utcnow().isoformat(),
            "duplicate_observers": self.detect_duplicate_observers(),
            "duplicate_protocols": self.detect_duplicate_protocols(),
            "turnout_anomalies": self.detect_turnout_anomalies(),
            "vote_share_anomalies": self.detect_vote_share_anomalies(),
            "timestamp_anomalies": self.detect_timestamp_anomalies(),
            "collusion_patterns": self.detect_collusion_patterns(),
            "geolocation_anomalies": self.detect_geolocation_anomalies()
        }
        
        # Подсчитать общее количество проблем по severity
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for category, items in results.items():
            if category == "scan_timestamp":
                continue
            
            for item in items:
                severity = item.get("severity", "LOW")
                if severity == "CRITICAL":
                    critical_count += 1
                elif severity == "HIGH":
                    high_count += 1
                elif severity == "MEDIUM":
                    medium_count += 1
                else:
                    low_count += 1
        
        results["summary"] = {
            "total_issues": critical_count + high_count + medium_count + low_count,
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count
        }
        
        return results
