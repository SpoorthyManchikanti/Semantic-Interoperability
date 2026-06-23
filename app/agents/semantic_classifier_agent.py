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

MEDICATION_DRUG_CLASSES = [
    "ACE Inhibitor", "ARB Antihypertensive", "Beta-Blocker", "Calcium Channel Blocker",
    "Diuretic", "Statin", "Anticoagulant", "Antiplatelet",
    "Antibiotic", "Antiviral", "Antifungal",
    "Bronchodilator Inhaler", "Inhaled Corticosteroid",
    "Antidiabetic", "Insulin",
    "Opioid Analgesic", "NSAID Analgesic", "Acetaminophen Analgesic",
    "Anticonvulsant", "Antidepressant", "Antipsychotic", "Anxiolytic",
    "Cholinesterase Inhibitor", "Thyroid Hormone Replacement",
    "Hormonal Contraceptive", "Hormone Replacement Therapy",
    "Immunosuppressant", "Chemotherapy",
    "Antihistamine", "Corticosteroid",
    "Proton Pump Inhibitor", "Antacid",
    "Nicotine Replacement Therapy", "Vitamin / Supplement",
    "Ophthalmic Medication", "Topical Medication",
    "Infusion / IV Solution",
]


def normalize_subcategory(subcategory: str) -> str:
    """Canonicalize subcategory formatting before DB insert."""
    if not subcategory:
        return subcategory
    sub = subcategory.replace('/', ' / ').replace('  ', ' ').strip()
    sub = ' / '.join(part.strip().title() for part in sub.split(' / '))
    return sub


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
            "Infectious Disease", "Mental Health", "Cardiovascular",
            "Neurology", "Musculoskeletal", "Endocrine",
            "Gastroenterology", "Obstetrics / Gynecology",
            "Pain Management", "Allergy / Immunology",
            "Dental / Oral Health", "Cancer",
            "Social Determinants", "General",
        ]

    return categories


def classify_concept(concept_name: str, categories: list[str], source_type: str = "") -> dict:
    """
    Classify a concept and return result dict including token usage.
    Returns: { category, subcategory, confidence, prompt_tokens, completion_tokens, needs_review }
    """

    if not concept_name or concept_name.strip().lower() in ("unknown", "n/a", "none", ""):
        return {
            "category": "General",
            "subcategory": "Unknown / Invalid Concept",
            "confidence": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "needs_review": True,
        }

    category_list = "\n".join(f"- {c}" for c in categories)

    medication_rules = ""
    if source_type == "medication":
        drug_class_list = "\n".join(f"  - {d}" for d in MEDICATION_DRUG_CLASSES)
        medication_rules = f"""
MEDICATION RULES (mandatory — this concept is a medication):
- subcategory MUST be a specific drug class. "Medication" alone is never valid.
- Choose from this list or write the closest equivalent in title case:
{drug_class_list}
- If the drug fits multiple classes, pick the primary therapeutic use.
"""

    prompt = f"""You are a healthcare semantic classification agent.

Classify the clinical concept below into exactly one category and one specific subcategory.

SOURCE TYPE: {source_type or "unknown"}
CONCEPT: {concept_name}

INSTRUCTIONS:
1. Choose the single most specific category from the allowed list.
2. subcategory must describe what this concept IS — be specific, not generic.
3. Use title case for subcategory. Use " / " (space-slash-space) as separator if combining terms.
4. "General" is a last resort — only use it if no other category fits.
5. Set confidence below 0.95 if the classification is genuinely ambiguous.
{medication_rules}
SUBCATEGORY EXAMPLES BY SOURCE TYPE:
- condition:   "Chronic Kidney Disease", "Community-Acquired Pneumonia", "Type 2 Diabetes Mellitus"
- observation: "Complete Blood Count / White Blood Cell Count", "Vital Signs / Heart Rate", "Urinalysis / Urine Ph"
- medication:  must follow the medication rules above

ALLOWED CATEGORIES:
{category_list}

Return JSON only — no explanation, no markdown:
{{
    "category": "",
    "subcategory": "",
    "confidence": 0.0
}}"""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.choices[0].message.content)
    result["subcategory"] = normalize_subcategory(result["subcategory"])
    result["prompt_tokens"] = response.usage.prompt_tokens
    result["completion_tokens"] = response.usage.completion_tokens
    result["needs_review"] = result["confidence"] < 0.95

    return result