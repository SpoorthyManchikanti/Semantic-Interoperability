import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import "./RelationshipGraph.css";

const TYPE_COLOR = {
  condition: "#A2493D",
  medication: "#3B4A6B",
  observation: "#4A6670",
  omop_concept: "#8A8A2D",
  patient: "#6B6B6B",
};

const DIM_COLOR = "#DEDBD2";
const DIM_LINK_COLOR = "rgba(222, 219, 208, 0.25)";
const NODE_RADIUS = 4;
const SEARCH_RING_COLOR = "#D9A441";
const LABEL_TEXT_COLOR = "#2B2F36";
const LABEL_BG_COLOR = "rgba(255, 255, 252, 0.88)";
// Below this many currently-visible nodes, show labels on all of them
// regardless of *which* filter(s) got it there — a boolean "is any filter
// on" check doesn't track density: unchecking just one type on a dense
// patient can still leave 100+ nodes, which is unreadable as text.
const LABEL_NODE_COUNT_THRESHOLD = 40;

// Edge color by relationship category — distinguishes "this patient has
// this concept" plumbing from OMOP mapping from genuine clinical semantics
// from identity-resolution duplicate links, all visually at a glance.
const PATIENT_OWNERSHIP_RELATIONSHIPS = new Set([
  "diagnosed_with",
  "is_on_medication",
  "has_observation",
]);

const EDGE_COLOR = {
  ownership: "#B7B2A5", // neutral/light grey — patient-to-concept plumbing
  maps_to: "#C9982F", // gold/amber — concept-to-OMOP mapping
  clinical: "#1F7A78", // bold teal — genuine Athena-documented clinical relationships
  duplicate: "#8B5FA3", // distinct purple — POTENTIAL_DUPLICATE_OF
};

function edgeCategory(relationship) {
  if (relationship === "maps_to") return "maps_to";
  if (relationship === "potential_duplicate_of") return "duplicate";
  if (PATIENT_OWNERSHIP_RELATIONSHIPS.has(relationship)) return "ownership";
  return "clinical";
}

// Node types the "one checkbox per type" filter row covers. Patient nodes
// are always shown — they aren't part of this filter set.
const FILTERABLE_TYPES = [
  { type: "condition", label: "Condition" },
  { type: "medication", label: "Medication" },
  { type: "observation", label: "Observation" },
  { type: "omop_concept", label: "OMOP Concept" },
];

// Edges that just say "this patient has this concept" / "this concept maps
// to this OMOP concept" — not a genuine concept-to-concept clinical
// relationship. Hidden by the "Clinical relationships only" toggle.
const NON_CLINICAL_RELATIONSHIPS = new Set([
  "diagnosed_with",
  "is_on_medication",
  "has_observation",
  "maps_to",
]);

function endpointId(endpoint) {
  return typeof endpoint === "object" && endpoint !== null ? endpoint.id : endpoint;
}

/**
 * Interactive nodes/edges relationship graph — type filters, clinical-only
 * toggle, in-graph search with ring highlight + auto zoom-to-fit, and
 * click-to-focus dimming. Labels are hover-only by default and only ever
 * become always-on for: search matches, the click-focused neighborhood, or
 * when the currently-visible node count drops below LABEL_NODE_COUNT_THRESHOLD
 * — there is deliberately no zoom-level trigger. Data-source agnostic: pass
 * any fetchGraph() that resolves to {nodes, edges}, keyed by reloadKey so it
 * knows when to refetch. Used by both the Patient Detail "Ontology
 * Relationships" tab (patient-centered) and the Semantic Explorer detail
 * panel (concept-centered).
 */
export default function RelationshipGraph({ fetchGraph, reloadKey, caption, emptyMessage, onLoaded, excludeNodeTypes = [] }) {
  const [rawData, setRawData] = useState(null);
  const [error, setError] = useState(null);
  const [typeFilters, setTypeFilters] = useState(() =>
    Object.fromEntries(FILTERABLE_TYPES.map((t) => [t.type, true]))
  );
  const [clinicalOnly, setClinicalOnly] = useState(false);
  const [focusNodeId, setFocusNodeId] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const containerRef = useRef(null);
  const fgRef = useRef(null);
  const [width, setWidth] = useState(600);
  const [height, setHeight] = useState(440);

  useEffect(() => {
    setFocusNodeId(null);
    setSearchTerm("");
    setRawData(null);
    setError(null);
    fetchGraph()
      .then((data) => {
        setRawData(data);
        onLoaded?.(data);
      })
      .catch((err) => setError(err.message || "Failed to load relationships"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  useEffect(() => {
    // containerRef only exists once rawData is loaded and the graph markup
    // mounts, so this must re-run after that happens — not just once on
    // initial mount, when the ref is still null.
    if (!containerRef.current) return;
    const observer = new ResizeObserver(([entry]) => {
      setWidth(entry.contentRect.width);
      setHeight(entry.contentRect.height);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [rawData]);

  const graphData = useMemo(() => {
    if (!rawData) return null;

    const typeAllowed = (type) => {
      if (excludeNodeTypes.includes(type)) return false;
      return type === "patient" || typeFilters[type];
    };
    const allowedNodeIds = new Set(rawData.nodes.filter((n) => typeAllowed(n.type)).map((n) => n.id));

    let links = rawData.edges.filter((e) => {
      if (clinicalOnly && NON_CLINICAL_RELATIONSHIPS.has(e.relationship)) return false;
      return allowedNodeIds.has(e.source) && allowedNodeIds.has(e.target);
    });

    let nodeIds;
    if (clinicalOnly) {
      // Only nodes still connected by a surviving (clinical) edge.
      nodeIds = new Set();
      links.forEach((l) => {
        nodeIds.add(l.source);
        nodeIds.add(l.target);
      });
    } else {
      nodeIds = allowedNodeIds;
    }

    const nodes = rawData.nodes.filter((n) => nodeIds.has(n.id)).map((n) => ({ ...n }));
    links = links.map((l) => ({ source: l.source, target: l.target, relationship: l.relationship }));

    return { nodes, links };
  }, [rawData, typeFilters, clinicalOnly, excludeNodeTypes]);

  const neighborMap = useMemo(() => {
    const map = new Map();
    if (!graphData) return map;
    graphData.links.forEach((l) => {
      const s = endpointId(l.source);
      const t = endpointId(l.target);
      if (!map.has(s)) map.set(s, new Set());
      if (!map.has(t)) map.set(t, new Set());
      map.get(s).add(t);
      map.get(t).add(s);
    });
    return map;
  }, [graphData]);

  const highlightedNodeIds = useMemo(() => {
    if (!focusNodeId) return null;
    return new Set([focusNodeId, ...(neighborMap.get(focusNodeId) || [])]);
  }, [focusNodeId, neighborMap]);

  const matchedNodeIds = useMemo(() => {
    if (!graphData || !searchTerm.trim()) return null;
    const term = searchTerm.trim().toLowerCase();
    return new Set(
      graphData.nodes.filter((n) => n.name?.toLowerCase().includes(term)).map((n) => n.id)
    );
  }, [graphData, searchTerm]);

  // Auto-center/zoom on whatever the search currently matches. A short
  // delay lets node positions settle from the last graphData/filter change
  // before we ask the force-graph instance for their coordinates.
  useEffect(() => {
    if (!fgRef.current || !matchedNodeIds || matchedNodeIds.size === 0) return;
    const id = setTimeout(() => {
      fgRef.current.zoomToFit(600, 80, (node) => matchedNodeIds.has(node.id));
    }, 250);
    return () => clearTimeout(id);
  }, [matchedNodeIds]);

  // Labels stay hover-only in the default dense view (too many to render as
  // text without clutter). Once filters/toggles have thinned the *actually
  // visible* node count down below the threshold — not just "some filter is
  // active", which says nothing about how dense the result still is — show
  // real always-on text instead of relying on hover.
  const showAllLabels = !!graphData && graphData.nodes.length > 0 && graphData.nodes.length < LABEL_NODE_COUNT_THRESHOLD;

  const handleSearchChange = (value) => {
    setFocusNodeId(null);
    setSearchTerm(value);
  };

  const toggleType = (type) => {
    setFocusNodeId(null);
    setTypeFilters((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  const toggleClinicalOnly = () => {
    setFocusNodeId(null);
    setClinicalOnly((prev) => !prev);
  };

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (!rawData) return <p className="no-data">Loading relationships…</p>;

  function renderFilters() {
    return (
      <div className="ontology-filters">
        {FILTERABLE_TYPES.map(({ type, label }) => (
          <label key={type}>
            <input
              type="checkbox"
              checked={typeFilters[type]}
              onChange={() => toggleType(type)}
            />
            <i style={{ background: TYPE_COLOR[type], width: 8, height: 8, borderRadius: "50%", display: "inline-block" }} />
            {label}
          </label>
        ))}
        <span className="filter-divider" />
        <label>
          <input type="checkbox" checked={clinicalOnly} onChange={toggleClinicalOnly} />
          Clinical relationships only
        </label>
      </div>
    );
  }

  if (!graphData || graphData.links.length === 0) {
    return (
      <div>
        {renderFilters()}
        <p className="no-data">{emptyMessage || "No graph relationships match the current filters."}</p>
      </div>
    );
  }

  return (
    <div>
      {caption && <p className="ontology-caption">{caption}</p>}
      {renderFilters()}
      <div className="ontology-search">
        <input
          type="text"
          placeholder="Search concept name…"
          value={searchTerm}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
        {searchTerm && (
          <button type="button" className="ontology-search-clear" onClick={() => handleSearchChange("")}>
            Clear
          </button>
        )}
        {matchedNodeIds && (
          <span className="ontology-search-count">
            {matchedNodeIds.size} match{matchedNodeIds.size === 1 ? "" : "es"}
          </span>
        )}
      </div>
      <div className="ontology-legend">
        <div className="legend-group">
          <span className="legend-group-title">Node types</span>
          <div className="legend-items">
            <span><i className="legend-dot" style={{ background: TYPE_COLOR.condition }} /> Condition</span>
            <span><i className="legend-dot" style={{ background: TYPE_COLOR.medication }} /> Medication</span>
            <span><i className="legend-dot" style={{ background: TYPE_COLOR.observation }} /> Observation</span>
            <span><i className="legend-dot" style={{ background: TYPE_COLOR.omop_concept }} /> OMOP Concept</span>
            <span><i className="legend-dot" style={{ background: TYPE_COLOR.patient }} /> Patient</span>
          </div>
        </div>
        <div className="legend-group">
          <span className="legend-group-title">Relationship types</span>
          <div className="legend-items">
            <span><i className="legend-line" style={{ background: EDGE_COLOR.ownership }} /> Patient ownership</span>
            <span><i className="legend-line" style={{ background: EDGE_COLOR.maps_to }} /> Maps to OMOP</span>
            <span><i className="legend-line" style={{ background: EDGE_COLOR.clinical }} /> Clinical relationship</span>
            <span><i className="legend-line" style={{ background: EDGE_COLOR.duplicate }} /> Potential duplicate</span>
          </div>
        </div>
      </div>
      <div className="ontology-graph" ref={containerRef}>
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={width}
          height={height}
          nodeLabel="name"
          nodeRelSize={NODE_RADIUS}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const isMatched = matchedNodeIds && matchedNodeIds.has(node.id);
            const isFocused = highlightedNodeIds && highlightedNodeIds.has(node.id);

            const baseColor = !highlightedNodeIds
              ? TYPE_COLOR[node.type] || "#8A8A85"
              : isFocused
                ? TYPE_COLOR[node.type] || "#8A8A85"
                : DIM_COLOR;

            ctx.beginPath();
            ctx.arc(node.x, node.y, NODE_RADIUS, 0, 2 * Math.PI);
            ctx.fillStyle = baseColor;
            ctx.fill();

            if (isMatched) {
              ctx.save();
              ctx.shadowColor = SEARCH_RING_COLOR;
              ctx.shadowBlur = 10;
              ctx.beginPath();
              ctx.arc(node.x, node.y, NODE_RADIUS + 3, 0, 2 * Math.PI);
              ctx.strokeStyle = SEARCH_RING_COLOR;
              ctx.lineWidth = 2;
              ctx.stroke();
              ctx.restore();
            }

            if (node.name && (isMatched || isFocused || showAllLabels)) {
              const fontSize = Math.max(4, 11 / globalScale);
              ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              const textWidth = ctx.measureText(node.name).width;
              const padX = 3 / globalScale;
              const padY = 1.5 / globalScale;
              const labelY = node.y + NODE_RADIUS + 3 / globalScale;
              ctx.fillStyle = LABEL_BG_COLOR;
              ctx.fillRect(node.x - textWidth / 2 - padX, labelY - padY, textWidth + padX * 2, fontSize + padY * 2);
              ctx.fillStyle = LABEL_TEXT_COLOR;
              ctx.fillText(node.name, node.x, labelY);
            }
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, NODE_RADIUS + 2, 0, 2 * Math.PI);
            ctx.fill();
          }}
          linkLabel={(l) => l.relationship}
          linkColor={(l) => {
            const baseColor = EDGE_COLOR[edgeCategory(l.relationship)];
            if (!highlightedNodeIds) return baseColor;
            const s = endpointId(l.source);
            const t = endpointId(l.target);
            return highlightedNodeIds.has(s) && highlightedNodeIds.has(t) ? baseColor : DIM_LINK_COLOR;
          }}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          cooldownTicks={80}
          onNodeClick={(node) => setFocusNodeId((prev) => (prev === node.id ? null : node.id))}
          onBackgroundClick={() => setFocusNodeId(null)}
        />
      </div>
    </div>
  );
}
