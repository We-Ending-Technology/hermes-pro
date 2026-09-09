import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
function App() {
  const [view, setView] = useState("Dashboard"); const [topic, setTopic] = useState("");
  const [data, setData] = useState({ jobs: 0, products: 0, running: 0, failures: 0, worker: "checking" });
  const [products, setProducts] = useState([]); const [jobs, setJobs] = useState([]); const [message, setMessage] = useState("");
  async function refresh() { try { const [d, p, j] = await Promise.all([fetch(`${API}/api/v1/dashboard`), fetch(`${API}/api/v1/products`), fetch(`${API}/api/v1/jobs`)]); setData(await d.json()); setProducts(await p.json()); setJobs(await j.json()); } catch { setMessage("API indisponível. Verifique VITE_API_URL e o backend."); } }
  useEffect(() => { refresh(); }, []);
  async function produce(event) { event.preventDefault(); setMessage("Produção iniciada..."); const response = await fetch(`${API}/api/v1/factory/produce`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic }) }); setMessage(response.ok ? "Produto concluído." : "Falha na produção."); setTopic(""); await refresh(); }
  const nav = ["Dashboard", "Fábrica", "Produtos", "Jobs", "Logs", "Configurações"];
  return <main className="app"><aside><span className="eyebrow">HERMES PRO</span><h1>Control room</h1>{nav.map(item => <button className={view === item ? "active" : ""} onClick={() => setView(item)} key={item}>{item}</button>)}</aside><section className="content"><header><div><span className="eyebrow">OPERATIONS</span><h2>{view}</h2></div><span className="status">Worker: {data.worker}</span></header>{message && <div className="notice">{message}</div>}{view === "Dashboard" && <><div className="cards">{[["Jobs", data.jobs], ["Produtos", data.products], ["Em andamento", data.running], ["Falhas", data.failures]].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}</div><p className="muted">Acompanhe a operação da fábrica em um único lugar.</p></>}{view === "Fábrica" && <form onSubmit={produce} className="factory"><label>Tema do produto<input value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: produtividade para equipes remotas" required minLength="3" /></label><button className="primary">Iniciar produção</button><p className="muted">O fluxo gera, revisa, valida e salva o produto. Publicação automática está desativada.</p></form>}{view === "Produtos" && <List items={products} empty="Nenhum produto produzido ainda." />}{view === "Jobs" && <List items={jobs} empty="Nenhum job criado ainda." />}{view === "Logs" && <p className="muted">Logs estruturados serão exibidos nesta área quando o worker persistente for ativado.</p>}{view === "Configurações" && <p className="muted">Providers, Supabase e origem da API são configurados por variáveis do backend. Nenhum secret é carregado no frontend.</p>}</section></main>
}
function List({ items, empty }) { return items.length ? <div className="list">{items.map(item => <pre key={item.id}>{JSON.stringify(item, null, 2)}</pre>)}</div> : <p className="muted">{empty}</p>; }
createRoot(document.getElementById("root")).render(<App />);
