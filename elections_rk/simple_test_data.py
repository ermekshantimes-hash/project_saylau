"""
Упрощённый скрипт для создания минимальных тестовых данных
"""

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Подключение к БД
DATABASE_URL = "postgresql://postgres:23june1970@localhost:5432/elections_rk"
engine = create_engine(DATABASE_URL)

def create_minimal_test_data():
    """Создать минимальные тестовые данные через SQL"""
    
    print("🔧 Создание тестовых данных...")
    
    with engine.connect() as conn:
        # Начать транзакцию
        trans = conn.begin()
        
        try:
            # 1. Создать выборы
            result = conn.execute(text("""
                INSERT INTO elections (name, election_date, election_type, created_at)
                VALUES (:name, :date, :type, :created)
                RETURNING id
            """), {
                "name": "Президентские выборы 2024",
                "date": (datetime.now() + timedelta(days=30)).date(),
                "type": "PRESIDENTIAL",
                "created": datetime.now()
            })
            election_id = result.fetchone()[0]
            print(f"✅ Создана выборы ID: {election_id}")
            
            # 2. Создать регионы
            regions_data = [
                ("Алматинская область", "01", "REGION"),
                ("г. Алматы", "19", "CITY"),
            ]
            
            region_ids = []
            for name, code, rtype in regions_data:
                result = conn.execute(text("""
                    INSERT INTO regions (name, code, type, parent_id)
                    VALUES (:name, :code, :type, NULL)
                    RETURNING id
                """), {"name": name, "code": code, "type": rtype})
                region_ids.append(result.fetchone()[0])
            
            print(f"✅ Создано регионов: {len(region_ids)}")
            
            # 3. Создать участки
            precinct_ids = []
            for i, region_id in enumerate(region_ids):
                for j in range(1, 4):
                    result = conn.execute(text("""
                        INSERT INTO precincts (number, region_id, address, registered_voters, latitude, longitude)
                        VALUES (:num, :region, :addr, :voters, :lat, :lon)
                        RETURNING id
                    """), {
                        "num": f"{i+1:02d}{j:03d}",
                        "region": region_id,
                        "addr": f"ул. Тестовая {j}",
                        "voters": 1000 + j * 100,
                        "lat": 51.1605 + (j * 0.01),
                        "lon": 71.4704 + (j * 0.01)
                    })
                    precinct_ids.append(result.fetchone()[0])
            
            print(f"✅ Создано участков: {len(precinct_ids)}")
            
            # 4. Создать кандидатов
            candidates_data = [
                ("Иванов Иван Иванович", "Партия Прогресса", 1),
                ("Петров Петр Петрович", "Народная Партия", 2),
                ("Сидорова Анна Сергеевна", "Партия Будущего", 3),
                ("Ахметов Нурлан Бекович", "Nur Otan", 4),
                ("Козлов Дмитрий Алексеевич", "Независимый", 5)
            ]
            
            candidate_ids = []
            for name, party, ballot_num in candidates_data:
                result = conn.execute(text("""
                    INSERT INTO candidates (election_id, name, party, ballot_number)
                    VALUES (:election, :name, :party, :ballot)
                    RETURNING id
                """), {
                    "election": election_id,
                    "name": name,
                    "party": party,
                    "ballot": ballot_num
                })
                candidate_ids.append(result.fetchone()[0])
            
            print(f"✅ Создано кандидатов: {len(candidate_ids)}")
            
            # Подтвердить транзакцию
            trans.commit()
            
            print("\n" + "=" * 60)
            print("✅ ВСЕ ДАННЫЕ СОЗДАНЫ УСПЕШНО!")
            print("=" * 60)
            print(f"\n📋 Информация для использования:")
            print(f"\n🗳️  Выборы:")
            print(f"   ID: {election_id}")
            print(f"   Название: Президентские выборы 2024")
            
            print(f"\n👥 Кандидаты:")
            for i, (name, party, _) in enumerate(candidates_data, start=1):
                print(f"   {i}. {name} ({party})")
            
            print(f"\n🏛️  Участки (примеры):")
            print(f"   Доступно участков с ID от {precinct_ids[0]} до {precinct_ids[-1]}")
            
            print(f"\n🚀 Откройте http://localhost:8000/upload.html")
            print(f"   - Выберите выборы: Президентские выборы 2024")
            print(f"   - Введите ID участка: {precinct_ids[0]} (или любой от {precinct_ids[0]} до {precinct_ids[-1]})")
            print(f"   - Загрузите любое изображение")
            print(f"   - Введите голоса для кандидатов")
            print("=" * 60)
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Ошибка: {e}")
            raise

if __name__ == "__main__":
    create_minimal_test_data()
