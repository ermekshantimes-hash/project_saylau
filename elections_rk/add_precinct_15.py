from app.database import SessionLocal
from app.models import Precinct

db = SessionLocal()

try:
    precinct = Precinct(id=15, region_id=1, precinct_number=15, address='Адрес участка 15', voters_registered=1000)
    db.add(precinct)
    db.commit()
    print('Precinct 15 added successfully')
except Exception as e:
    print(f'Error: {e}')
    db.rollback()
finally:
    db.close()