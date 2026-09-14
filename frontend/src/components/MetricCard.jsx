export default function MetricCard({ label, value, hint }) { return <article className="metric"><span>{label}</span><strong>{value}</strong>{hint && <small>{hint}</small>}</article>; }
