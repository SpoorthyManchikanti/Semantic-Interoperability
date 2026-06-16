#!/usr/bin/env python
"""Run ETL pipeline: create tables then load data."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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
