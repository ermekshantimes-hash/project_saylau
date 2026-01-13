"""
Скрипт для создания тестовых данных
Создаёт выборы, регионы, участки и кандидатов для тестирования
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import sys
import os

# Добавить путь к app
sys.path.insert(0, os.path.abspath('.'))

from app.models import Base, Election, Region, Precinct
from app.models_extended import Candidate
from app.config import settings

# Создать движок и сессию
engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
db = Session()

def create_test_data():
    """Создать тестовые данные"""
    
    print("🔧 Создание тестовых данных...")
    
    # 1. Создать выборы
    election = Election(
        name="Президентские выборы 2024",
        election_date=datetime.now() + timedelta(days=30),
        election_type="PRESIDENTIAL"
    )
    db.add(election)
    db.flush()
    print(f"✅ Создана выборы: {election.name} (ID: {election.id})")
    
    # 2. Создать регионы
    regions_data = [
        {"name": "Алматинская область", "code": "01"},
        {"name": "Акмолинская область", "code": "02"},
        {"name": "г. Алматы", "code": "19"},
        {"name": "г. Астана", "code": "71"}
    ]
    
    regions = []
    for r_data in regions_data:
        region = Region(
            name=r_data["name"],
            code=r_data["code"],
            parent_id=None
        )
        db.add(region)
        regions.append(region)
    
    db.flush()
    print(f"✅ Создано регионов: {len(regions)}")
    
    # 3. Создать участки (по 3 на регион)
    precincts = []
    for region in regions:
        for i in range(1, 4):
            precinct = Precinct(
                number=f"{region.code}{i:03d}",
                region_id=region.id,
                address=f"ул. Тестовая {i}, {region.name}",
                registered_voters=1000 + i * 100,
                latitude=51.1605 + (i * 0.01),
                longitude=71.4704 + (i * 0.01)
            )
            db.add(precinct)
            precincts.append(precinct)
    
    db.flush()
    print(f"✅ Создано участков: {len(precincts)}")
    
    # 4. Создать кандидатов
    candidates_data = [
        {"name": "Иванов Иван Иванович", "party": "Партия Прогресса"},
        {"name": "Петров Петр Петрович", "party": "Народная Партия"},
        {"name": "Сидорова Анна Сергеевна", "party": "Партия Будущего"},
        {"name": "Ахметов Нурлан Бекович", "party": "Nur Otan"},
        {"name": "Козлов Дмитрий Алексеевич", "party": "Независимый"}
    ]
    
    candidates = []
    for idx, c_data in enumerate(candidates_data, start=1):
        candidate = Candidate(
            election_id=election.id,
            name=c_data["name"],
            party=c_data["party"],
            ballot_number=idx
        )
        db.add(candidate)
        candidates.append(candidate)
    
    db.flush()
    print(f"✅ Создано кандидатов: {len(candidates)}")
    
    # Сохранить всё
    db.commit()
    print("\n✅ Все тестовые данные успешно созданы!\n")
    
    # Вывести информацию для пользователя
    print("=" * 60)
    print("📋 ИНФОРМАЦИЯ ДЛЯ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"\n🗳️  Выборы ID: {election.id}")
    print(f"   Название: {election.name}")
    print(f"\n👥 Кандидаты ({len(candidates)}):")
    for c in candidates:
        print(f"   ID {c.id}: {c.name} ({c.party})")
    
    print(f"\n🏛️  Участки (примеры):")
    for p in precincts[:5]:
        print(f"   ID {p.id}, Номер {p.number}: {p.address}")
    
    print(f"\n📝 Для загрузки протокола используйте:")
    print(f"   - Election ID: {election.id}")
    print(f"   - Precinct ID: {precincts[0].id} (или любой от {precincts[0].id} до {precincts[-1].id})")
    print("=" * 60)

if __name__ == "__main__":
    try:
        create_test_data()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
        raise
    finally:
        db.close()
