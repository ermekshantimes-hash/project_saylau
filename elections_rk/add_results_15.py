from app.database import SessionLocal
from app.models import PrecinctResult, ElectionSubject

db = SessionLocal()

try:
    subjects = db.query(ElectionSubject).filter(ElectionSubject.election_id == 1).all()
    votes_data = [100, 50, 30, 20, 10, 5, 80, 40, 25, 15, 8, 3]  # Sample votes
    
    for i, subject in enumerate(subjects):
        result = PrecinctResult(
            election_id=1,
            precinct_id=15,
            subject_id=subject.id,
            votes=votes_data[i] if i < len(votes_data) else 10
        )
        db.add(result)
    
    db.commit()
    print('Precinct results for 15 added successfully')
except Exception as e:
    print(f'Error: {e}')
    db.rollback()
finally:
    db.close()