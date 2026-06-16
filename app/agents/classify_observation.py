from sqlalchemy import text

from app.database import engine

with engine.begin() as conn:

    rows = conn.execute(
        text("""
            SELECT DISTINCT observation_name
            FROM observations
            LIMIT 10
        """)
    )

    observations = [r[0] for r in rows]

print(observations)