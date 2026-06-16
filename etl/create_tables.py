from sqlalchemy import text
from app.database import engine

def create_tables():

    with engine.begin() as conn:

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            gender TEXT,
            birth_date DATE
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS conditions (
            id SERIAL PRIMARY KEY,
            patient_id TEXT,
            condition_name TEXT
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS observations (
            id SERIAL PRIMARY KEY,
            patient_id TEXT,
            observation_name TEXT,
            observation_value TEXT
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS medications (
            id SERIAL PRIMARY KEY,
            patient_id TEXT,
            medication_name TEXT
        );
        """))

    print("Tables created successfully.")

if __name__ == "__main__":
    create_tables()