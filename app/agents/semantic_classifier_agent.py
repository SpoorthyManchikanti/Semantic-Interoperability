import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
import json

from dotenv import load_dotenv
from openai import AzureOpenAI
from sqlalchemy import text

from app.database import engine

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")


def fetch_categories() -> list[str]:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT DISTINCT category FROM concepts WHERE category IS NOT NULL"
        ))
        categories = [row[0] for row in result]

    if not categories:
        categories = [
            "Vitals", "Diabetes", "Lipids", "Kidney Function",
            "Liver Function", "Hematology", "Respiratory",
            "Infectious Disease", "Mental Health",
            "Social Determinants", "Cancer", "General"
        ]

    return categories


def classify_concept(concept_name: str, categories: list[str]) -> dict:
    """
    Classify a concept and return result dict including token usage.
    Returns: { category, subcategory, confidence, prompt_tokens, completion_tokens }
    """
    category_list = "\n".join(f"- {c}" for c in categories)

    prompt = f"""
You are a healthcare semantic classification agent.

Classify the clinical concept below.

Concept:
{concept_name}

Choose the most appropriate category.

Allowed Categories:

{category_list}

Return JSON only:

{{
    "category":"",
    "subcategory":"",
    "confidence":0.0
}}
"""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.choices[0].message.content)

    # Attach token usage to result
    result["prompt_tokens"] = response.usage.prompt_tokens
    result["completion_tokens"] = response.usage.completion_tokens

    return result