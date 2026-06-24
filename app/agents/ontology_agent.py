from app.tools.ontology_tool import OntologyTool
from app.db_models.ontology import (
    OntologyNode,
    OntologyEdge,
    OntologyGraph
)


class OntologyAgent:

    def __init__(self, ontology_tool: OntologyTool):
        self.ontology_tool = ontology_tool

    def expand_concept(
        self,
        concept_id: str,
        include_relationships: bool = True,
        include_ancestors: bool = True,
        include_synonyms: bool = True
    ) -> OntologyGraph:

        concept = self.ontology_tool.get_concept(concept_id)

        if not concept:
            return OntologyGraph(nodes=[], edges=[])

        node = OntologyNode(
            concept_id=concept["concept_id"],
            concept_name=concept["concept_name"],
            vocabulary_id=concept.get("vocabulary_id")
        )

        nodes = [node]
        edges = []

        # -------------------------
        # Relationships
        # -------------------------

        if include_relationships:

            relationships = self.ontology_tool.get_relationships(
                concept_id
            )

            for rel in relationships:

                edges.append(
                    OntologyEdge(
                        source_concept_id=rel["concept_id_1"],
                        target_concept_id=rel["concept_id_2"],
                        relationship_type=rel["relationship_id"]
                    )
                )

        # -------------------------
        # Ancestors
        # -------------------------

        if include_ancestors:

            ancestors = self.ontology_tool.get_ancestors(
                concept_id
            )

            for ancestor in ancestors:

                ancestor_id = ancestor["ancestor_concept_id"]

                ancestor_concept = (
                    self.ontology_tool.get_concept(
                        ancestor_id
                    )
                )

                if ancestor_concept:

                    nodes.append(
                        OntologyNode(
                            concept_id=ancestor_concept["concept_id"],
                            concept_name=ancestor_concept["concept_name"],
                            vocabulary_id=ancestor_concept.get(
                                "vocabulary_id"
                            )
                        )
                    )

        return OntologyGraph(
            nodes=nodes,
            edges=edges
        )

    def run(self, concept_ids: list[str]):

        graphs = []

        for concept_id in concept_ids:

            graph = self.expand_concept(
                concept_id=concept_id
            )

            graphs.append(graph)

        return graphs

