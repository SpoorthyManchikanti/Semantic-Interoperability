import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";

const TYPE_COLOR = {
  condition: "#A2493D",
  medication: "#3B4A6B",
  observation: "#4A6670",
};

const PREVIEW_HEIGHT = 220;

export default function KnowledgeGraphPreview({ graph }) {
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const fgRef = useRef(null);
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
    <div className="kg-preview" ref={containerRef} onClick={() => navigate("/explorer")} role="button" tabIndex={0}>
      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        width={width}
        height={PREVIEW_HEIGHT}
        nodeLabel="name"
        nodeColor={(n) => TYPE_COLOR[n.type] || "#8A8A85"}
        nodeRelSize={3.5}
        linkColor={(l) => (hoverNode && (l.source.id === hoverNode || l.target.id === hoverNode)) ? "#3B4A6B" : "#DEDBD2"}
        onNodeHover={(n) => setHoverNode(n?.id ?? null)}
        cooldownTicks={60}
        // The node cluster is roughly circular but the frame is a wide
        // rectangle, so a plain zoomToFit is capped by the shorter (height)
        // dimension and leaves visible empty space left/right. Fit tight
        // first, then push the zoom in further so the cluster actually
        // fills the frame — some peripheral nodes may crop at the edges,
        // which is fine for a decorative, non-interactive preview.
        onEngineStop={() => {
          const fg = fgRef.current;
          if (!fg) return;
          fg.zoomToFit(400, 8);
          setTimeout(() => fg.zoom(fg.zoom() * 1.6, 300), 450);
        }}
        enableZoomInteraction={false}
        enablePanInteraction={false}
      />
      <span className="kg-preview-hint">Click to explore concepts and relationships &#8594;</span>
    </div>
  );
}
