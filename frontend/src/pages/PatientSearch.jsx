import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { searchPatients } from "../api";
import "./PatientSearch.css";

function SearchResults({ q }) {
  const navigate = useNavigate();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    searchPatients({ q })
      .then(setResults)
      .catch((err) => setError(err.message || "Search failed"))
      .finally(() => setLoading(false));
  }, [q]);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (loading) return <p className="no-data">Searching…</p>;

  return (
    <section className="data-section full-width">
      <div className="section-head">
        <h3>Results for &ldquo;{q}&rdquo;</h3>
        <span className="count-chip">{results.length}</span>
      </div>
      <div className="item-list">
        {results.length === 0
          ? <p className="no-data">No patients matched. Try a shorter fragment of the name or ID.</p>
          : results.map((p) => (
            <button
              key={p.patient_id}
              className="patient-result-row"
              onClick={() => navigate(`/patients/${p.patient_id}`)}
            >
              <span className="item-name">{p.first_name} {p.last_name}</span>
              <span className="badge cat-badge">{p.gender}</span>
              <span className="code-inline mono">{p.patient_id}</span>
            </button>
          ))}
      </div>
    </section>
  );
}

export default function PatientSearch() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(q);

  function onSearch(e) {
    e.preventDefault();
    const value = query.trim();
    if (!value) return;
    navigate(`/patients?q=${encodeURIComponent(value)}`);
  }

  return (
    <div className="patient-search-page">
      <section className="search-section">
        <h2 className="page-title">Patient search</h2>
        <p className="page-subtitle">
          Search by full or partial name, or patient ID — matches anywhere in the field, not just exact.
        </p>
        <form className="search-bar" onSubmit={onSearch}>
          <input
            className="search-input"
            placeholder="Search by name or patient ID..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <button className="search-btn" type="submit" disabled={!query.trim()}>
            Search
          </button>
        </form>
      </section>

      {q && <SearchResults key={q} q={q} />}
    </div>
  );
}
