import sys
import os
from sqlalchemy import create_engine, inspect
from app.config import settings
from app import models, models_extended

def verify_schema():
    print(f"Checking database at: {settings.database_url}")
    
    # Create engine
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    
    engine = create_engine(settings.database_url, connect_args=connect_args)
    
    # Inspect tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print(f"Found {len(existing_tables)} tables in database.")
    
    # Expected tables from models and models_extended
    expected_tables = [
        "elections", "regions", "precincts", "election_subjects", 
        "protocol_photos", "precinct_results",
        "organizations", "candidates", "users", "observer_profiles",
        "observer_applications", "observer_checkins", "protocols",
        "protocol_items", "precinct_tallies", "incidents", "audit_events"
    ]
    
    missing_tables = []
    for table in expected_tables:
        if table in existing_tables:
            print(f"[OK] Table '{table}' exists")
        else:
            print(f"[ERROR] Table '{table}' MISSING")
            missing_tables.append(table)
            
    if missing_tables:
        print(f"\nFAILED: {len(missing_tables)} tables are missing!")
        sys.exit(1)
    else:
        print("\nSUCCESS: All expected tables found.")
        sys.exit(0)

if __name__ == "__main__":
    # Ensure we can import app
    sys.path.append(os.getcwd())
    verify_schema()
