"""
ПРОСТОЙ скрипт для создания тестовых данных через прямой SQL
Использует только существующие колонки из реальной схемы БД
"""

import psycopg2
from datetime import datetime, timedelta

# Параметры подключения
DB_PARAMS = {
    "dbname": "elections_rk",
    "user": "postgres",
    "password": "23june1970",
    "host": "localhost",
    "port": "5432"
}

def create_data():
    """Создать тестовые данные"""
    
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    try:
        print("🔧 Создание тестовых данных...\n")
        
        # 1. Выборы
        cur.execute("""
            INSERT INTO elections (name, election_date, election_type, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            "Президентские выборы 2024",
            (datetime.now() + timedelta(days=30)).date(),
            "PRESIDENTIAL",
            datetime.now()
        ))
        election_id = cur.fetchone()[0]
        print(f"✅ Выборы ID: {election_id}")
        
        # 2. Регионы (используем правильную структуру)
        cur.execute("""
            INSERT INTO regions (name, code, type, parent_id)
            VALUES
                ('Алматинская область', '01', 'REGION', NULL),
                ('г. Алматы', '19', 'CITY', NULL)
            RETURNING id
        """)
        region_ids = [row[0] for row in cur.fetchall()]
        print(f"✅ Регионы: {region_ids}")
        
        # 3. Участки (проверим какие колонки есть)
        # Используем минимальный набор обязательных полей
        precinct_ids = []
        for idx, region_id in enumerate(region_ids):
            for i in range(1, 4):
                cur.execute("""
                    INSERT INTO precincts (precinct_number, region_id, address, registered_voters, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    f"{idx+1:02d}{i:03d}",
                    region_id,
                    f"ул. Тестовая {i}",
                    1000 + i * 100,
                    51.1605 + (i * 0.01),
                    71.4704 + (i * 0.01)
                ))
                precinct_ids.append(cur.fetchone()[0])
        
        print(f"✅ Участки: {len(precinct_ids)} шт")
        
        # 4. Кандидаты
        candidates = [
            ("Иванов Иван Иванович", "Партия Прогресса", 1),
            ("Петров Петр Петрович", "Народная Партия", 2),
            ("Сидорова Анна Сергеевна", "Партия Будущего", 3),
        ]
        
        candidate_ids = []
        for name, party, ballot in candidates:
            cur.execute("""
                INSERT INTO candidates (election_id, name, party, ballot_number)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (election_id, name, party, ballot))
            candidate_ids.append(cur.fetchone()[0])
        
        print(f"✅ Кандидаты: {len(candidate_ids)} чел\n")
        
        # Подтвердить изменения
        conn.commit()
        
        # Вывести инфо
        print("=" * 70)
        print("✅ УСПЕШНО! Данные созданы!\n")
        print(f"🗳️  Выборы: Президентские выборы 2024 (ID: {election_id})")
        print(f"\n👥 Кандидаты:")
        for i, (name, party, _) in enumerate(candidates):
            print(f"   {i+1}. {name} - {party}")
        
        print(f"\n🏛️  Участки (ID от {precinct_ids[0]} до {precinct_ids[-1]})")
        
        print(f"\n🚀 ОТКРОЙТЕ: http://localhost:8000/upload.html")
        print(f"   1. Выберите: Президентские выборы 2024")
        print(f"   2. ID участка: {precinct_ids[0]} (или любой)")
        print(f"   3. Загрузите любое фото (JPG/PNG)")
        print(f"   4. Введите голоса (например: 450, 320, 180)")
        print("=" * 70)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Ошибка: {e}")
        print("\nПопробуем исправить...")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_data()
