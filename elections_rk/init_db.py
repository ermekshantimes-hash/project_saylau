import sys
import os
# Add current directory to path
sys.path.append(os.getcwd())

from app.database import engine
from app import models, models_extended

def init_db():
    print("Initializing database...")
    # Create all tables
    models.Base.metadata.create_all(bind=engine)
    print("Database initialized.")

if __name__ == "__main__":
    init_db()
