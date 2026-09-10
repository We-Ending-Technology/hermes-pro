import { useEffect, useState } from "react";
import { diagnose } from "./api";

export default function Diagnostics({ onRetry }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true); setError("");
    try { setData(await diagnose()); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { run(); }, []);
  const statusLabel = s => ({ online: "ONLINE", ready: "READY", offline: "OFFLINE", not_configured: "NÃO CONFIGURADO", error: "ERRO" }[s] || s?.toUpperCase());

  return <section className="diagnostics panel">
    <div className="section-heading"><div><span className="kicker violet">SYSTEM STATUS</span><h3>Diagnóstico de infraestrutura</h3></div><button className="text-button" onClick={run} disabled={loading}>{loading ? "Testando…" : "↻ Testar novamente"}</button></div>
    <div className="diagnostic-grid">{(data?.checks || []).map((item, i) => <article className={`diagnostic-item ${item.status}`} key={`${item.name}-${i}`}><div><strong>{item.name}</strong><p>{item.message || "—"}</p></div><span>{statusLabel(item.status)}</span>{item.latency_ms != null && <small>{item.latency_ms} ms</small>}</article>)}</div>
    {error && <div className="diagnostic-error"><strong>Último erro</strong><p>{error}</p></div>}
    {data && <p className="panel-note">Última verificação: {new Date(data.timestamp).toLocaleString("pt-BR")} · {data.elapsed_ms} ms</p>}
    <button className="text-button" onClick={onRetry}>↻ Atualizar painel</button>
  </section>;
}
