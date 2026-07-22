"""Neo4j Aura connectivity for the FastAPI backend.

Mirrors the singleton pattern used for the Postgres `engine` in
app/database.py. Same Aura instance and credentials scripts/load_to_neo4j.py
writes to.
"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def get_neo4j_session():
    return driver.session()
