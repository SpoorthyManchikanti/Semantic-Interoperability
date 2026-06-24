#!/usr/bin/env python3
"""
Quick test: Classify a single concept and display results.

Usage:
    python scripts/test_classifier.py
    python scripts/test_classifier.py "Hemoglobin A1C"
"""

import sys
from app.agents.semantic_classifier import classify_concept

def main():
    # Default test concept or use command-line argument
    concept = sys.argv[1] if len(sys.argv) > 1 else "Blood Pressure"
    
    print(f"\nClassifying: {concept}\n")
    
    result = classify_concept(concept)
    
    print(f"Category:     {result['category']}")
    print(f"Subcategory:  {result['subcategory']}")
    print(f"Confidence:   {result['confidence']}\n")


if __name__ == "__main__":
    main()
