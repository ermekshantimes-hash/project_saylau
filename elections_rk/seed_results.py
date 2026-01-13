from app.database import SessionLocal
from app.models_extended import PrecinctTally, TallyBasis, TallyStatus
from datetime import datetime
import random

db = SessionLocal()

try:
    # Получить первые 100 УИК и всех кандидатов
    from app.models import Precinct
    from app.models_extended import Candidate
    
    precincts = db.query(Precinct).limit(100).all()
    candidates = db.query(Candidate).all()  # Все кандидаты
    
    print(f'Найдено {len(precincts)} УИК')
    print(f'Найдено {len(candidates)} кандидатов')
    
    if not candidates:
        print('ОШИБКА: Нет кандидатов! Проверьте таблицу candidates')
        exit(1)
    
    total_created = 0
    
    for precinct in precincts:
        # Случайное количество голосов (от 200 до 1500)
        total_votes = random.randint(200, 1500)
        remaining = total_votes
        
        for i, candidate in enumerate(candidates):
            # Последнему кандидату отдаем остаток
            if i == len(candidates) - 1:
                votes = remaining
            else:
                # Случайная доля (5-30%)
                votes = random.randint(int(remaining * 0.05), int(remaining * 0.30))
                remaining -= votes
            
            tally = PrecinctTally(
                precinct_id=precinct.id,
                candidate_id=candidate.id,
                votes=votes,
                basis=TallyBasis.PROTOCOL,  # Используем enum
                status=TallyStatus.VERIFIED,  # Используем enum
                version=1,
                created_at=datetime.now()
            )
            db.add(tally)
            db.flush()  # Flush после каждой записи
            total_created += 1
        
        # Коммит после каждого УИК
        db.commit()
        
        if precinct.id % 10 == 0:
            print(f'Обработано {precinct.id} УИК...')
    
    print(f'\n✅ Успешно создано {total_created} записей результатов!')
    
    # Проверка
    from sqlalchemy import func
    result = db.query(func.sum(PrecinctTally.votes)).scalar()
    print(f'Всего голосов: {result:,}')
    
except Exception as e:
    print(f'❌ Ошибка: {e}')
    db.rollback()
finally:
    db.close()
