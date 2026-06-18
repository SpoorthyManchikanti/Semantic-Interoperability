import os
from typing import List

from pydantic import BaseModel
from dotenv import load_dotenv

from openai import AzureOpenAI

load_dotenv()


client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview",  # FIX: must be 2024-08-01-preview or later for structured outputs
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

MODEL_NAME = DEPLOYMENT


class Edge(BaseModel):
    model_config = {"extra": "forbid"}
 
    source: str
    edge_type: str
    target: str
    confidence: float
    evidence_sources: list[str]
    
 
 
class EdgeCollection(BaseModel):
    model_config = {"extra": "forbid"}
 
    edges: list[Edge]

# TOOLS
def cooccurrence_tool(patient_data):
    # Replace with real implementation
    return [
        {
            "source": "Type 2 Diabetes",
            "target": "Metformin",
            "support": 0.42,
            "lift": 3.1
        }
    ]


def ontology_tool(concepts):
    # Replace with SNOMED / RxNorm / UMLS lookup
    return [
        {
            "source": "Metformin",
            "edge_type": "ISA",
            "target": "Biguanide"
        }
    ]


def guideline_tool(concepts):
    # Replace with guideline extraction
    return [
        {
            "source": "Type 2 Diabetes",
            "edge_type": "FIRST_LINE_TREATMENT",
            "target": "Metformin"
        }
    ]


# AGENT
class RelationshipDiscoveryAgent:

    SYSTEM_PROMPT = """
You are a clinical relationship discovery agent.

Identify clinically meaningful relationships.

Allowed edge types:

ISA
TREATED_WITH
MONITORED_BY
RISK_FACTOR_FOR
COMPLICATION_OF
CONTRAINDICATION_FOR
ASSOCIATED_WITH
CO_OCCURS_WITH

Return JSON only.
"""

    def run(self, concepts, patient_data) -> List[Edge]:

        cooccurrence_results = cooccurrence_tool(patient_data)
        ontology_results = ontology_tool(concepts)
        guideline_results = guideline_tool(concepts)

        prompt = f"""
Concepts:

{concepts}

Co-occurrence evidence:

{cooccurrence_results}

Ontology evidence:

{ontology_results}

Guideline evidence:

{guideline_results}

Produce a list of edges with:

source
edge_type
target
confidence
evidence_sources
metadata
"""

        # FIX: Use beta.chat.completions.parse() instead of client.responses.parse()
        # FIX: Use messages= instead of input=, and response_format= instead of text_format=
        response = client.beta.chat.completions.parse(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format=EdgeCollection  # FIX: response_format= instead of text_format=
        )

        # FIX: Access result via choices[0].message.parsed instead of output_parsed
        return response.choices[0].message.parsed.edges


# EXAMPLE RUN
if __name__ == "__main__":

    concepts = [
        "Type 2 Diabetes",
        "Metformin",
        "HbA1c",
        "Obesity"
    ]

    patient_data = {}

    agent = RelationshipDiscoveryAgent()

    edges = agent.run(concepts, patient_data)

    for edge in edges:
        print(edge.model_dump())
