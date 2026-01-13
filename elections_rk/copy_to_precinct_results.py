from app.database import SessionLocal
from app.models import PrecinctResult, Election, Precinct
from app.models_extended import PrecinctTally, Candidate
from sqlalchemy import func

db = SessionLocal()

try:
    print("Копирование данных из precinct_tallies в precinct_results...")
    
    # Получить election_id для кандидатов
    # Так как у Candidate нет election_id, используем первые выборы
    election_id = 1
    
    # Получить все результаты из precinct_tallies
    tallies = db.query(PrecinctTally).filter(PrecinctTally.status == 'VERIFIED').all()
    
    print(f"Найдено {len(tallies)} результатов в precinct_tallies")
    
    if not tallies:
        print("ОШИБКА: Нет данных в precinct_tallies!")
        exit(1)
    
    # Проверить, есть ли election_subjects для этих кандидатов
    from app.models import ElectionSubject
    
    created = 0
    for tally in tallies:
        # Найти или создать ElectionSubject для кандидата
        candidate = db.query(Candidate).filter(Candidate.id == tally.candidate_id).first()
        if not candidate:
            continue
        
        subject = db.query(ElectionSubject).filter(
            ElectionSubject.election_id == election_id,
            ElectionSubject.name == candidate.name
        ).first()
        
        if not subject:
            # Создать ElectionSubject
            subject = ElectionSubject(
                election_id=election_id,
                name=candidate.name,
                subject_type='candidate',
                ballot_number=tally.candidate_id
            )
            db.add(subject)
            db.flush()
        
        # Создать PrecinctResult
        existing = db.query(PrecinctResult).filter(
            PrecinctResult.election_id == election_id,
            PrecinctResult.precinct_id == tally.precinct_id,
            PrecinctResult.subject_id == subject.id
        ).first()
        
        if not existing:
            result = PrecinctResult(
                election_id=election_id,
                precinct_id=tally.precinct_id,
                subject_id=subject.id,
                votes=tally.votes
            )
            db.add(result)
            created += 1
        
        if created % 100 == 0:
            print(f"Создано {created} записей...")
            db.commit()
    
    db.commit()
    print(f"\n✅ Успешно создано {created} записей в precinct_results!")
    
    # Проверка
    total = db.query(func.sum(PrecinctResult.votes)).filter(
        PrecinctResult.election_id == election_id
    ).scalar()
    print(f"Всего голосов в precinct_results: {total:,}")
    
except Exception as e:
    print(f"ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
