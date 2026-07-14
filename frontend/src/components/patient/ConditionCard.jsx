export default function ConditionCard({ condition }) {
  const name = typeof condition === "string" ? condition : condition.condition_name;
  const category = typeof condition === "object" ? condition.category : null;
  const subcategory = typeof condition === "object" ? condition.subcategory : null;
  const code = typeof condition === "object" ? condition.snomed_code : null;
  const confidence = typeof condition === "object" && condition.confidence != null
    ? Math.round(condition.confidence * 100)
    : null;
  return (
    <div className="item-card condition-card">
      <span className="item-name">
        <span className="name-text">{name}</span>
        {code && <span className="code-inline">SNOMED: {code}</span>}
      </span>
      <div className="item-badges">
        {category && <span className="badge cat-badge">{category}</span>}
        {subcategory && <span className="badge subcat-badge">{subcategory}</span>}
        {confidence != null && <span className="badge conf-badge">{confidence}%</span>}
      </div>
    </div>
  );
}
