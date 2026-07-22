import { getPatientGraph } from "../../../api";
import RelationshipGraph from "../../graph/RelationshipGraph";

export default function OntologyTab({ patientId }) {
  return (
    <RelationshipGraph
      reloadKey={patientId}
      fetchGraph={() => getPatientGraph(patientId)}
      caption={
        <>
          This patient&rsquo;s real Athena/OMOP-documented picture from the knowledge graph: their diagnosed
          conditions, medications, and observations; each concept&rsquo;s mapping to a standard OMOP concept; genuine
          clinical relationships between their concepts (is-a hierarchy, due-to, associated-finding, etc., as
          documented in the OMOP vocabulary); and any potential duplicate patient links.
        </>
      }
      emptyMessage="No graph relationships found for this patient."
    />
  );
}
