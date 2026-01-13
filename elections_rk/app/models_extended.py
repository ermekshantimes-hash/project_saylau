# Расширенные модели для платформы наблюдателей (12K УИК)
# Согласно ТЗ: роли, организации, наблюдатели, инциденты, аудит

from sqlalchemy import (
    Column, Integer, String, Text, Date, TIMESTAMP, Boolean, Float, JSON,
    ForeignKey, UniqueConstraint, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models import Base


# ==================== ENUMS ====================

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    COORD = "COORD"  # Координатор НПО/штаба
    OBSERVER = "OBSERVER"  # Наблюдатель
    MEDIA = "MEDIA"  # Журналист/партнёр
    PUBLIC = "PUBLIC"  # Публичный пользователь


class OrganizationType(str, enum.Enum):
    PARTY = "PARTY"
    OO = "OO"  # Общественная организация
    IP = "IP"  # Инициативная группа
    INDEPENDENT = "INDEPENDENT"


class ObserverLegalType(str, enum.Enum):
    ORG = "ORG"  # От организации
    DELEGATE = "DELEGATE"  # Делегат
    INDEPENDENT = "INDEPENDENT"


class ObserverStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    BANNED = "BANNED"


class ApplicationStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    RESERVE = "RESERVE"
    ASSIGNED = "ASSIGNED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ApplicationSource(str, enum.Enum):
    ORG = "ORG"
    SELF = "SELF"
    NGO = "NGO"


class ShiftType(str, enum.Enum):
    FULL = "FULL"
    MORNING = "MORNING"
    EVENING = "EVENING"


class ProtocolStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"


class ProtocolSource(str, enum.Enum):
    PHOTO = "PHOTO"
    SCAN = "SCAN"
    CSV = "CSV"
    API = "API"


class TallyBasis(str, enum.Enum):
    PROTOCOL = "PROTOCOL"
    CORRECTION = "CORRECTION"


class TallyStatus(str, enum.Enum):
    PRELIM = "PRELIM"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"


class IncidentType(str, enum.Enum):
    BLOCK_ENTRY = "BLOCK_ENTRY"
    DOC_TAKEN = "DOC_TAKEN"
    BALLOT_STUFFING = "BALLOT_STUFFING"
    OTHER = "OTHER"


class IncidentSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class IncidentStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class AuditScope(str, enum.Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"


# ==================== MODELS ====================

class Organization(Base):
    """Организации (партии, ОО, ИГ)"""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    type = Column(SQLEnum(OrganizationType), nullable=False)
    short_name = Column(String(100), nullable=False)
    full_name = Column(Text, nullable=False)
    color_idx = Column(Integer)  # Индекс цвета из HSL-палитры
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)


class Candidate(Base):
    """Кандидаты"""
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    organization = relationship("Organization")


class User(Base):
    """Пользователи системы"""
    __tablename__ = "users"
    __table_args__ = (
        Index('idx_user_phone', 'phone'),
        Index('idx_user_email', 'email'),
    )

    id = Column(Integer, primary_key=True)
    phone = Column(String(20), unique=True)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255), nullable=False)  # Argon2id
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.PUBLIC)
    
    # MFA
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret = Column(String(32))  # TOTP secret
    
    # Статус и метаданные
    status = Column(String(20), nullable=False, default='ACTIVE')
    device_fingerprint = Column(Text)
    last_login_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)


class ObserverProfile(Base):
    """Профиль наблюдателя (KYC)"""
    __tablename__ = "observer_profiles"
    __table_args__ = (
        Index('idx_observer_user', 'user_id'),
        Index('idx_observer_status', 'status'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Тип наблюдателя
    legal_type = Column(SQLEnum(ObserverLegalType), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"))
    
    # Документы (хеши для безопасности)
    id_doc_type = Column(String(50))  # паспорт/ID-карта
    id_doc_number = Column(String(50))
    id_scan_hash = Column(String(64))  # SHA256
    selfie_hash = Column(String(64))  # SHA256 селфи-видео
    
    # Обучение и верификация
    training_passed = Column(Boolean, nullable=False, default=False)
    training_score = Column(Integer)
    training_completed_at = Column(TIMESTAMP)
    
    # Рейтинг и риск
    rating = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)  # 0-1, чем выше - тем подозрительнее
    
    # Статус
    status = Column(SQLEnum(ObserverStatus), nullable=False, default=ObserverStatus.DRAFT)
    verified_by = Column(Integer, ForeignKey("users.id"))
    verified_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization")
    verifier = relationship("User", foreign_keys=[verified_by])


class ObserverApplication(Base):
    """Заявки наблюдателей на УИК"""
    __tablename__ = "observer_applications"
    __table_args__ = (
        Index('idx_app_precinct', 'precinct_id', 'status'),
        Index('idx_app_observer', 'observer_id', 'status'),
    )

    id = Column(Integer, primary_key=True)
    observer_id = Column(Integer, ForeignKey("observer_profiles.id"), nullable=False)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    
    # Источник и приоритет
    source = Column(SQLEnum(ApplicationSource), nullable=False)
    priority = Column(Integer, default=0)  # Чем выше - тем важнее
    shift = Column(SQLEnum(ShiftType), nullable=False, default=ShiftType.FULL)
    
    # Статус
    status = Column(SQLEnum(ApplicationStatus), nullable=False, default=ApplicationStatus.REQUESTED)
    
    # Координатор, назначивший
    assigned_by = Column(Integer, ForeignKey("users.id"))
    assigned_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)

    observer = relationship("ObserverProfile")
    precinct = relationship("Precinct")
    coordinator = relationship("User")


class ObserverCheckin(Base):
    """Чек-ин наблюдателей на УИК"""
    __tablename__ = "observer_checkins"
    __table_args__ = (
        Index('idx_checkin_precinct', 'precinct_id', 'ts_in'),
    )

    id = Column(Integer, primary_key=True)
    observer_id = Column(Integer, ForeignKey("observer_profiles.id"), nullable=False)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    
    # Время
    ts_in = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    ts_out = Column(TIMESTAMP)
    
    # Верификация
    qrcode_token = Column(String(255))  # JWT-токен из QR
    selfie_hash = Column(String(64))  # Селфи при входе
    device_fingerprint = Column(Text)
    geo_lat = Column(Float)
    geo_lon = Column(Float)
    
    verified_by = Column(Integer, ForeignKey("users.id"))
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    observer = relationship("ObserverProfile")
    precinct = relationship("Precinct")
    verifier = relationship("User")


class Protocol(Base):
    """Протоколы (расширенная версия)"""
    __tablename__ = "protocols"
    __table_args__ = (
        Index('idx_protocol_precinct', 'precinct_id', 'status'),
        Index('idx_protocol_uploader', 'uploader_id'),
    )

    id = Column(Integer, primary_key=True)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Файл
    file_url = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256
    file_size = Column(Integer)
    
    # Метаданные
    exif_json = Column(JSON)  # EXIF данные
    ocr_json = Column(JSON)  # Результаты OCR
    
    # Версионирование
    version = Column(Integer, nullable=False, default=1)
    source = Column(SQLEnum(ProtocolSource), nullable=False, default=ProtocolSource.PHOTO)
    
    # Статус и верификация
    status = Column(SQLEnum(ProtocolStatus), nullable=False, default=ProtocolStatus.DRAFT)
    verified_by = Column(Integer, ForeignKey("users.id"))
    verified_at = Column(TIMESTAMP)
    verification_notes = Column(Text)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)

    precinct = relationship("Precinct")
    uploader = relationship("User", foreign_keys=[uploader_id])
    verifier = relationship("User", foreign_keys=[verified_by])


class ProtocolItem(Base):
    """Строки протокола (голоса по кандидатам)"""
    __tablename__ = "protocol_items"

    id = Column(Integer, primary_key=True)
    protocol_id = Column(Integer, ForeignKey("protocols.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("election_subjects.id"), nullable=False)
    votes = Column(Integer, nullable=False)

    protocol = relationship("Protocol")
    candidate = relationship("ElectionSubject", foreign_keys=[candidate_id])


class PrecinctTally(Base):
    """Подсчёт по УИК (агрегаты)"""
    __tablename__ = "precinct_tallies"
    __table_args__ = (
        Index('idx_tally_precinct', 'precinct_id', 'status'),
        Index('idx_tally_candidate', 'candidate_id'),
    )

    id = Column(Integer, primary_key=True)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    votes = Column(Integer, nullable=False)
    
    # Основание
    basis = Column(SQLEnum(TallyBasis), nullable=False, default=TallyBasis.PROTOCOL)
    protocol_id = Column(Integer, ForeignKey("protocols.id"))
    
    # Статус и версия
    status = Column(SQLEnum(TallyStatus), nullable=False, default=TallyStatus.PRELIM)
    version = Column(Integer, nullable=False, default=1)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    precinct = relationship("Precinct")
    candidate = relationship("Candidate")
    protocol = relationship("Protocol")


class Incident(Base):
    """Инциденты"""
    __tablename__ = "incidents"
    __table_args__ = (
        Index('idx_incident_precinct', 'precinct_id', 'status'),
        Index('idx_incident_severity', 'severity', 'status'),
    )

    id = Column(Integer, primary_key=True)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Тип и серьёзность
    type = Column(SQLEnum(IncidentType), nullable=False)
    severity = Column(SQLEnum(IncidentSeverity), nullable=False, default=IncidentSeverity.MEDIUM)
    
    # Описание и медиа
    description = Column(Text, nullable=False)
    media_urls = Column(JSON)  # Массив URL фото/видео
    
    # Статус и SLA
    status = Column(SQLEnum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN)
    sla_deadline = Column(TIMESTAMP)
    
    # Модерация
    assigned_to = Column(Integer, ForeignKey("users.id"))
    resolution_notes = Column(Text)
    resolved_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)

    precinct = relationship("Precinct")
    reporter = relationship("User", foreign_keys=[reporter_id])
    assignee = relationship("User", foreign_keys=[assigned_to])


class AuditEvent(Base):
    """Аудит-лог (append-only)"""
    __tablename__ = "audit_events"
    __table_args__ = (
        Index('idx_audit_ts', 'ts'),
        Index('idx_audit_actor', 'actor_user_id'),
    )

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    
    # Область и тип события
    scope = Column(SQLEnum(AuditScope), nullable=False)
    event_type = Column(String(100), nullable=False)
    
    # Полезная нагрузка
    payload_json = Column(JSON)
    
    # Хеширование для неизменяемости
    ts = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    hash = Column(String(64), nullable=False)  # SHA256 этой записи
    prev_hash = Column(String(64))  # Хеш предыдущей записи (цепочка)

    actor = relationship("User")
