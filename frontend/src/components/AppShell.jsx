import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useTheme } from "../lib/useTheme";
import "./AppShell.css";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/ingest", label: "Ingest Patient" },
  { to: "/patients", label: "Patients" },
  { to: "/admin", label: "Admin Review" },
  { to: "/explorer", label: "Semantic Explorer" },
  { to: "/ontology", label: "Ontology Browser" },
];

function useBreadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  if (segments.length === 0) return [{ label: "Dashboard", to: "/" }];
  const crumbs = [{ label: "Platform", to: "/" }];
  let path = "";
  for (const seg of segments) {
    path += `/${seg}`;
    const navMatch = NAV_ITEMS.find((n) => n.to === path);
    crumbs.push({ label: navMatch ? navMatch.label : decodeURIComponent(seg), to: path });
  }
  return crumbs;
}

export default function AppShell() {
  const { theme, toggleTheme } = useTheme();
  const crumbs = useBreadcrumbs();
  const navigate = useNavigate();
  const [globalQuery, setGlobalQuery] = useState("");
  const [navOpen, setNavOpen] = useState(false);

  function onGlobalSearch(e) {
    e.preventDefault();
    const q = globalQuery.trim();
    if (!q) return;
    navigate(`/patients?q=${encodeURIComponent(q)}`);
  }

  return (
    <div className="shell">
      {navOpen && <div className="shell-sidebar-backdrop" onClick={() => setNavOpen(false)} />}

      <aside className={`shell-sidebar${navOpen ? " open" : ""}`}>
        <div className="brand">
          <div className="brand-icon">SI</div>
          <div className="brand-text">
            <span className="brand-title">Semantic Interoperability</span>
            <span className="brand-sub">Patient Intelligence Platform</span>
          </div>
        </div>
        <nav className="shell-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) => `shell-nav-item${isActive ? " active" : ""}${item.stub ? " stub" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="shell-body">
        <header className="shell-topbar">
          <button
            className="shell-nav-toggle"
            onClick={() => setNavOpen((open) => !open)}
            aria-label={navOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={navOpen}
          >
            <span />
            <span />
            <span />
          </button>

          <nav className="breadcrumbs" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <span key={c.to} className="breadcrumb-item">
                {i > 0 && <span className="breadcrumb-sep">/</span>}
                {i === crumbs.length - 1
                  ? <span className="breadcrumb-current">{c.label}</span>
                  : <NavLink to={c.to}>{c.label}</NavLink>}
              </span>
            ))}
          </nav>

          <form className="global-search" onSubmit={onGlobalSearch}>
            <input
              placeholder="Search patients or concepts..."
              value={globalQuery}
              onChange={(e) => setGlobalQuery(e.target.value)}
              aria-label="Global search"
            />
          </form>

          <button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </header>

        <main className="shell-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
