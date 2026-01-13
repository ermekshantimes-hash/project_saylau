from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("1. Очистка precinct_results...")
    conn.execute(text("DELETE FROM precinct_results WHERE election_id = 1"))
    conn.commit()
    
    print("2. Создание election_subjects...")
    result = conn.execute(text("""
        INSERT INTO election_subjects (election_id, name, subject_type, ballot_number)
        SELECT DISTINCT 
            1 as election_id,
            c.name,
            'candidate' as subject_type,
            c.id as ballot_number
        FROM candidates c
        WHERE NOT EXISTS (
            SELECT 1 FROM election_subjects es 
            WHERE es.election_id = 1 AND es.name = c.name
        )
        RETURNING id
    """))
    created_subjects = result.rowcount
    conn.commit()
    print(f"   Создано {created_subjects} election_subjects")
    
    print("3. Копирование данных...")
    result = conn.execute(text("""
        INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes)
        SELECT 
            1 as election_id,
            pt.precinct_id,
            es.id as subject_id,
            SUM(pt.votes) as votes
        FROM precinct_tallies pt
        JOIN candidates c ON pt.candidate_id = c.id
        JOIN election_subjects es ON es.name = c.name AND es.election_id = 1
        WHERE pt.status = 'VERIFIED'
        GROUP BY pt.precinct_id, es.id
    """))
    copied = result.rowcount
    conn.commit()
    print(f"   Скопировано {copied} записей")
    
    print("4. Проверка...")
    result = conn.execute(text("""
        SELECT 
            COUNT(*) as count,
            SUM(votes) as total_votes
        FROM precinct_results
        WHERE election_id = 1
    """))
    row = result.fetchone()
    print(f"   Записей: {row[0]:,}")
    print(f"   Всего голосов: {row[1]:,}")
    
print("\n✅ Готово!")
