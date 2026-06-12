from sqlalchemy import *

from app.database import engine

metadata = MetaData()

patients = Table(
    "patients",
    metadata,

    Column("patient_id", String, primary_key=True),
    Column("first_name", String),
    Column("last_name", String),
    Column("gender", String)
)

conditions = Table(
    "conditions",
    metadata,

    Column("id", Integer, primary_key=True),
    Column("patient_id", String),
    Column("condition_name", String)
)

observations = Table(
    "observations",
    metadata,

    Column("id", Integer, primary_key=True),
    Column("patient_id", String),
    Column("observation_name", String),
    Column("value", String)
)

metadata.create_all(engine)