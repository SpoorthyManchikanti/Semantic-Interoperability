import { Routes, Route } from "react-router-dom";
import AppShell from "./components/AppShell";
import Dashboard from "./pages/Dashboard";
import PatientSearch from "./pages/PatientSearch";
import PatientDetail from "./pages/PatientDetail";
import AdminReview from "./pages/AdminReview";
import OntologyBrowser from "./pages/OntologyBrowser";
import ComingSoon from "./pages/ComingSoon";
import "./App.css";

const STUBS = [
  { path: "/explorer", title: "Semantic Explorer", description: "Search clinical concepts directly — SNOMED/LOINC/RxNorm codes, synonyms, related diseases, medications, and labs — instead of starting from a patient." },
  { path: "/knowledge-graph", title: "Knowledge Graph", description: "Full-screen zoom/pan graph explorer across every patient, concept, and relationship in the platform, with search, filters, and a mini-map." },
  { path: "/data-quality", title: "Data Quality", description: "Duplicate records, missing codes, mapping failures, and validation errors across the pipeline." },
];

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/patients" element={<PatientSearch />} />
        <Route path="/patients/:patientId" element={<PatientDetail />} />
        <Route path="/admin" element={<AdminReview />} />
        <Route path="/ontology" element={<OntologyBrowser />} />
        {STUBS.map((s) => (
          <Route
            key={s.path}
            path={s.path}
            element={<ComingSoon title={s.title} description={s.description} />}
          />
        ))}
      </Route>
    </Routes>
  );
}
