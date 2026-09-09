import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const nav = [["⌂", "Dashboard"], ["✦", "Fábrica"], ["▣", "Produtos"], ["◷", "Jobs"], ["≡", "Logs"], ["⚙", "Configurações"]];

function App() {
  const [view, setView] = useState("Dashboard");
  const [topic, setTopic] = useState("");
  const [data, setData] = useState({ jobs: 0, products: 0, running: 0, failures: 0, worker: "checking" });
  const [products, setProducts] = useState([]); const [jobs, setJobs] = useState([]);
  const [message, setMessage] = useState(""); const [loading, setLoading] = useState(false);

  async function refresh() {
    try {
      const [d, p, j] = await Promise.all([fetch(`${API}/api/v1/dashboard`), fetch(`${API}/api/v1/products`), fetch(`${API}/api/v1/jobs`)]);
      setData(await d.json()); setProducts(await p.json()); setJobs(await j.json());
    } catch { setMessage("API indisponível. Verifique VITE_API_URL e o backend."); }
  }
  useEffect(() => { refresh(); }, []);
  async function produce(event) {
    event.preventDefault(); setLoading(true); setMessage("Produção iniciada...");
    try {
      const response = await fetch(`${API}/api/v1/factory/produce`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic }) });
      setMessage(response.ok ? "Produto concluído com sucesso." : "Falha na produção."); if (response.ok) setTopic(""); await refresh();
    } catch { setMessage("Não foi possível conectar ao backend."); } finally { setLoading(false); }
  }
  return <main className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">H</div><div><strong>HERMES</strong><span>PRO</span></div></div><div className="sidebar-label">WORKSPACE</div><nav>{nav.map(([icon, label]) => <button className={view === label ? "nav-item active" : "nav-item"} onClick={() => setView(label)} key={label}><span className="nav-icon">{icon}</span><span>{label}</span></button>)}</nav><div className="sidebar-footer"><span className="live-dot" /> Sistema operacional</div></aside>
    <section className="main-content"><header className="topbar"><div><span className="eyebrow">HERMES PRO / CONTROL ROOM</span><h1>{view}</h1></div><div className="top-status"><span className="live-dot" /> <span>Online</span><button className="refresh" onClick={refresh}>↻</button></div></header>
      {message && <div className="notice">{message}</div>}
      {view === "Dashboard" && <Dashboard data={data} products={products} onFactory={() => setView("Fábrica")} />}
      {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} produce={produce} loading={loading} />}
      {view === "Produtos" && <ListView title="Produtos gerados" items={products} empty="Nenhum produto produzido ainda." />}
      {view === "Jobs" && <ListView title="Fila de produção" items={jobs} empty="Nenhum job criado ainda." />}
      {view === "Logs" && <EmptyPanel title="Logs" text="Logs estruturados serão exibidos nesta área quando o worker persistente for ativado." />}
      {view === "Configurações" && <EmptyPanel title="Configurações" text="Providers, Supabase e origem da API são configurados por variáveis do backend. Nenhum secret é carregado no frontend." />}
    </section></main>;
}
function Dashboard({ data, products, onFactory }) { const cards = [["Jobs", data.jobs, "◷"], ["Produtos", data.products, "▣"], ["Em andamento", data.running, "↗"], ["Falhas", data.failures, "!"]]; return <><section className="hero"><div><span className="eyebrow">MÁQUINA DE PRODUÇÃO</span><h2>Transforme uma ideia<br />em um produto digital.</h2><p>Centralize a operação do Hermes Pro em um único painel.</p></div><button className="primary large" onClick={onFactory}>＋ Criar produto</button></section><div className="cards">{cards.map(([label, value, icon]) => <article className="metric" key={label}><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong></article>)}</div><section className="section-head"><div><span className="eyebrow">VISÃO GERAL</span><h3>Atividade recente</h3></div><span className="muted">{products.length} produto(s)</span></section><div className="panel"><div className="panel-row"><span>Worker</span><strong className="status-ok">● {data.worker}</strong></div><div className="panel-row"><span>Produtos disponíveis</span><strong>{data.products}</strong></div><div className="panel-row"><span>Jobs processados</span><strong>{data.jobs}</strong></div></div></>; }
function Factory({ topic, setTopic, produce, loading }) { return <section className="factory-page"><div className="factory-copy"><span className="eyebrow">FÁBRICA DE DINHEIRO</span><h2>Qual produto você quer criar?</h2><p>Digite um tema e use o fluxo de produção que já existe no Hermes Pro.</p></div><form onSubmit={produce} className="factory-card"><label>TEMA DO PRODUTO<input value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: Marketing Digital" required minLength="3" /></label><button className="primary" disabled={loading}>{loading ? "Produzindo..." : "✦ Iniciar produção"}</button><p className="muted">O fluxo gera, revisa, valida e salva o produto. Publicação automática permanece desativada.</p></form></section>; }
function ListView({ title, items, empty }) { return <section><div className="section-head"><div><span className="eyebrow">HERMES PRO</span><h3>{title}</h3></div></div>{items.length ? <div className="list">{items.map(item => <pre key={item.id}>{JSON.stringify(item, null, 2)}</pre>)}</div> : <div className="empty">{empty}</div>}</section>; }
function EmptyPanel({ title, text }) { return <section><div className="section-head"><div><span className="eyebrow">HERMES PRO</span><h3>{title}</h3></div></div><div className="empty">{text}</div></section>; }
createRoot(document.getElementById("root")).render(<App />);
