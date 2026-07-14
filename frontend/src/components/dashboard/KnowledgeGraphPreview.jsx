import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";

const TYPE_COLOR = {
  condition: "#A2493D",
  medication: "#3B4A6B",
  observation: "#4A6670",
};

export default function KnowledgeGraphPreview({ graph }) {
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const [width, setWidth] = useState(400);
  const [hoverNode, setHoverNode] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const data = { nodes: graph.nodes, links: graph.edges.map((e) => ({ source: e.source, target: e.target, relationship: e.relationship })) };

  return (
    <div className="kg-preview" ref={containerRef} onClick={() => navigate("/knowledge-graph")} role="button" tabIndex={0}>
      <ForceGraph2D
        graphData={data}
        width={width}
        height={280}
        nodeLabel="name"
        nodeColor={(n) => TYPE_COLOR[n.type] || "#8A8A85"}
        nodeRelSize={3.5}
        linkColor={(l) => (hoverNode && (l.source.id === hoverNode || l.target.id === hoverNode)) ? "#3B4A6B" : "#DEDBD2"}
        onNodeHover={(n) => setHoverNode(n?.id ?? null)}
        cooldownTicks={60}
        enableZoomInteraction={false}
        enablePanInteraction={false}
      />
      <span className="kg-preview-hint">Click to open full Knowledge Graph &#8594;</span>
    </div>
  );
}
