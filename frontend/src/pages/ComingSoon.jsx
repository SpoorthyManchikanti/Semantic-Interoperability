export default function ComingSoon({ title, description }) {
  return (
    <div className="coming-soon">
      <h2>{title}</h2>
      <p>{description}</p>
      <span className="coming-soon-badge">Planned — next phase</span>
    </div>
  );
}
