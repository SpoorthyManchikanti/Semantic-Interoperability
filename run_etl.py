#!/usr/bin/env python
"""Run ETL pipeline: create tables then load data."""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Run create tables
print("=" * 60)
print("STEP 1: Creating tables in Neon PostgreSQL")
print("=" * 60)
from etl.create_tables import create_tables
create_tables()

print("\n")

# Run load data
print("=" * 60)
print("STEP 2: Loading Synthea data from JSON files")
print("=" * 60)
from etl.load_data import main
main()

print("\n")
print("=" * 60)
print("ETL Pipeline Complete!")
print("=" * 60)
