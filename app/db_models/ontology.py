from dataclasses import dataclass


@dataclass
class OntologyNode:
    concept_id: str
    concept_name: str
    vocabulary_id: str | None = None


@dataclass
class OntologyEdge:
    source_concept_id: str
    target_concept_id: str
    relationship_type: str


@dataclass
class OntologyGraph:
    nodes: list[OntologyNode]
    edges: list[OntologyEdge]