from app.database import SessionLocal
from app import models

db = SessionLocal()
try:
    regions = db.query(models.Region).filter(
        models.Region.parent_id.is_(None)
    ).all()
    
    result = [
        {
            "id": r.id,
            "name": r.name,
            "code": r.code,
            "type": r.type
        }
        for r in regions
    ]
    
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
finally:
    db.close()
