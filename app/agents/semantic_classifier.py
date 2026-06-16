import os
import json

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT"
)

def classify_concept(concept_name):

    prompt = f"""
You are a healthcare semantic classification agent.

Classify the clinical concept below.

Concept:
{concept_name}

Choose the most appropriate category.

Allowed Categories:

- Vitals
- Diabetes
- Lipids
- Kidney Function
- Liver Function
- Hematology
- Respiratory
- Infectious Disease
- Mental Health
- Social Determinants
- Cancer
- General

Return JSON only:

{{
    "category":"",
    "subcategory":"",
    "confidence":0.0
}}
"""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        response_format={"type":"json_object"},
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )

    return json.loads(
        response.choices[0].message.content
    )