export default function MedicationCard({ medication }) {
  const name = typeof medication === "string" ? medication : medication.medication_name;
  const category = typeof medication === "object" ? medication.category : null;
  const subcategory = typeof medication === "object" ? medication.subcategory : null;
  const code = typeof medication === "object" ? medication.rxnorm_code : null;
  const confidence = typeof medication === "object" && medication.confidence != null
    ? Math.round(medication.confidence * 100)
    : null;
  return (
    <div className="item-card medication-card">
      <span className="item-name">
        <span className="name-text">{name}</span>
        {code && <span className="code-inline">RxNorm: {code}</span>}
      </span>
      <div className="item-badges">
        {category && <span className="badge cat-badge">{category}</span>}
        {subcategory && <span className="badge subcat-badge">{subcategory}</span>}
        {confidence != null && <span className="badge conf-badge">{confidence}%</span>}
      </div>
    </div>
  );
}
