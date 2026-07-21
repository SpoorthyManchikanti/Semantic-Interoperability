import { useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { getPatientRelationships } from "../../../api";

const TYPE_COLOR = {
  condition: "#A2493D",
  medication: "#3B4A6B",
  observation: "#4A6670",
};

export default function OntologyTab({ patientId }) {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);
  const containerRef = useRef(null);
  const [width, setWidth] = useState(600);

  useEffect(() => {
    getPatientRelationships(patientId)
      .then((data) => setGraph({
        nodes: data.nodes,
        links: data.edges.map((e) => ({ source: e.source, target: e.target, relationship: e.relationship })),
      }))
      .catch((err) => setError(err.message || "Failed to load relationships"));
  }, [patientId]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (!graph) return <p className="no-data">Loading relationships…</p>;
  if (graph.nodes.length === 0) return <p className="no-data">No co-occurrence relationships found for this patient.</p>;

  return (
    <div>
      <p className="ontology-caption">
        Real co-occurrence relationships between this patient&rsquo;s classified conditions, medications, and
        observations. Not an OMOP is-a hierarchy — edges are derived from concepts sharing this patient&rsquo;s record.
      </p>
      <div className="ontology-legend">
        <span><i style={{ background: TYPE_COLOR.condition }} /> Condition</span>
        <span><i style={{ background: TYPE_COLOR.medication }} /> Medication</span>
        <span><i style={{ background: TYPE_COLOR.observation }} /> Observation</span>
      </div>
      <div className="ontology-graph" ref={containerRef}>
        <ForceGraph2D
          graphData={graph}
          width={width}
          height={440}
          nodeLabel="name"
          nodeColor={(n) => TYPE_COLOR[n.type] || "#8A8A85"}
          nodeRelSize={4}
          linkLabel={(l) => l.relationship}
          linkColor={() => "#DEDBD2"}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          cooldownTicks={80}
        />
      </div>
    </div>
  );
}
