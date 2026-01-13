from sqlalchemy import (
    Column, Integer, String, Text, Date, TIMESTAMP, Boolean,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

# РАСШИРЕННЫЕ МОДЕЛИ для системы наблюдателей определены в models_extended.py:
# - Organization, Candidate, User (RBAC с 5 ролями)
# - ObserverProfile (KYC, документы, обучение, рейтинг)
# - ObserverApplication (заявки на УИК, слоты, приоритеты)
# - ObserverCheckin (QR чек-ин с геолокацией)
# - Protocol, ProtocolItem (протоколы с OCR, версионированием)
# - PrecinctTally (агрегаты голосов)
# - Incident (инциденты с типами, серьёзностью, SLA)
# - AuditEvent (аппенд-онли лог с хеш-цепочками)


class Election(Base):
    __tablename__ = "elections"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    election_date = Column(Date, nullable=False)
    election_type = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    subjects = relationship("ElectionSubject", back_populates="election")


class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    code = Column(Text)
    type = Column(String(20), nullable=False)
    parent_id = Column(Integer, ForeignKey("regions.id"))

    parent = relationship("Region", remote_side=[id], backref="children")


class Precinct(Base):
    __tablename__ = "precincts"

    id = Column(Integer, primary_key=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    precinct_number = Column(Integer, nullable=False)
    address = Column(Text)
    voters_registered = Column(Integer)

    region = relationship("Region")


class ElectionSubject(Base):
    __tablename__ = "election_subjects"

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    name = Column(Text, nullable=False)
    subject_type = Column(String(20), nullable=False)
    ballot_number = Column(Integer)

    election = relationship("Election", back_populates="subjects")


class ProtocolPhoto(Base):
    __tablename__ = "protocol_photos"

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    image_url = Column(Text, nullable=False)
    uploaded_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    ocr_raw_text = Column(Text)
    parsed = Column(Boolean, nullable=False, default=False)


class PrecinctResult(Base):
    __tablename__ = "precinct_results"
    __table_args__ = (
        UniqueConstraint("election_id", "precinct_id", "subject_id",
                         name="uix_precinct_result"),
    )

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    precinct_id = Column(Integer, ForeignKey("precincts.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("election_subjects.id"), nullable=False)
    votes = Column(Integer, nullable=False)
