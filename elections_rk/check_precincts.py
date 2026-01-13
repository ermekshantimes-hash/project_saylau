from app.database import SessionLocal
from app import models
from sqlalchemy import func

db = SessionLocal()
regions = db.query(
    models.Precinct.region_id, 
    func.count(models.Precinct.id)
).group_by(
    models.Precinct.region_id
).limit(10).all()

for r in regions:
    print(f"Region {r[0]}: {r[1]} precincts")

db.close()
