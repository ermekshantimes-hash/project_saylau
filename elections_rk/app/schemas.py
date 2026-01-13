from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime


class SubjectResult(BaseModel):
    subject_id: int
    subject_name: str
    votes: int


class ProtocolCreateResponse(BaseModel):
    id: int
    precinct_id: int
    election_id: int
    image_url: str


class PrecinctPublicResult(BaseModel):
    precinct_id: int
    precinct_number: int
    region_path: str
    subjects: List[SubjectResult]
    protocol_photos: List[str]


class AggregatedRow(BaseModel):
    level_name: str   # "РК" / "Атырауская область" / "Алматы, Бостандыкский р-н" ...
    level_type: str   # 'country', 'region', 'district', 'local'
    subject_id: int
    subject_name: str
    votes: int


class AggregatedResponse(BaseModel):
    election_id: int
    election_name: str
    level: str           # 'country' | 'region' | 'district' | 'local'
    rows: List[AggregatedRow]


class ElectionInfo(BaseModel):
    id: int
    name: str
    election_date: date
    election_type: str
    created_at: datetime


class ElectionSubjectInfo(BaseModel):
    id: int
    name: str
    subject_type: str
    ballot_number: Optional[int]


class RegionInfo(BaseModel):
    id: int
    name: str
    code: Optional[str]
    type: str
    parent_id: Optional[int]
    children_count: int = 0
