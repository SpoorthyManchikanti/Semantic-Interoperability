import { useEffect, useState } from "react";
import {
  getDashboardSummary, getDashboardPipeline, getActivity, getGraphPreview,
  getDataSourceSummary,
} from "../api";
import KpiGrid from "../components/dashboard/KpiGrid";
import PipelineStatus from "../components/dashboard/PipelineStatus";
import KnowledgeGraphPreview from "../components/dashboard/KnowledgeGraphPreview";
import ActivityFeed from "../components/dashboard/ActivityFeed";
import DataSourceBadge from "../components/DataSourceBadge";
import "./Dashboard.css";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [activity, setActivity] = useState(null);
  const [graph, setGraph] = useState(null);
  const [dataSourceBreakdown, setDataSourceBreakdown] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getDashboardSummary(),
      getDashboardPipeline(),
      getActivity(50),
      getGraphPreview(30),
    ])
      .then(([s, p, a, g]) => {
        setSummary(s);
        setPipeline(p);
        setActivity(a);
        setGraph(g);
      })
      .catch((err) => setError(err.message || "Failed to load dashboard data"));

    // Fetched separately — a failure here shouldn't block the rest of the dashboard.
    getDataSourceSummary().then(setDataSourceBreakdown).catch(() => setDataSourceBreakdown([]));
  }, []);

  if (error) {
    return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  }

  if (!summary || !pipeline || !activity || !graph) {
    return <p className="no-data">Loading executive dashboard…</p>;
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h2 className="page-title">Executive Dashboard</h2>
        <p className="page-subtitle">
          Real-time view of the semantic interoperability lifecycle — FHIR ingestion through AI-powered
          classification, OMOP mapping, and knowledge graph relationships.
        </p>
        <DataSourceBadge breakdown={dataSourceBreakdown} />
      </div>

      <KpiGrid summary={summary} />

      <section className="dashboard-section">
        <h3 className="dashboard-section-title">Semantic pipeline status</h3>
        <PipelineStatus pipeline={pipeline} />
      </section>

      <div className="dashboard-two-col">
        <section className="dashboard-section">
          <h3 className="dashboard-section-title">Knowledge graph preview</h3>
          <KnowledgeGraphPreview graph={graph} />
        </section>

        <section className="dashboard-section">
          <h3 className="dashboard-section-title">Platform activity</h3>
          <p className="dashboard-section-caption">
            A historical snapshot of the original ingestion run, not a live/ongoing activity stream.
          </p>
          <ActivityFeed events={activity} />
        </section>
      </div>
    </div>
  );
}
