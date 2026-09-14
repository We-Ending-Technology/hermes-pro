import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-m7wd.onrender.com";
const nav = ["Início", "Hermes", "Fábrica", "Produtos", "Jobs", "Agentes"];

function App() {
  const [view, setView] = useState("Início");
  const [topic, setTopic] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState([]);
  const [products, setProducts] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [online, setOnline] = useState(false);
  const [notice, setNotice] = useState("");

  async function refresh() {
    try {
      const [h, p, j] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/api/v1/products`),
        fetch(`${API}/api/v1/jobs`),
      ]);
      setOnline(h.ok);
      if (p.ok) setProducts(await p.json());
      if (j.ok) setJobs(await j.json());
    } catch { setOnline(false); }
  }
  useEffect(() => { refresh(); const id = setInterval(refresh, 8000); return () => clearInterval(id); }, []);

  async function createProduct(e) {
    e.preventDefault();
    const value = topic.trim();
    if (!value) return;
    setNotice("Hermes recebeu o produto. A fábrica começou a trabalhar.");
    try {
      const r = await fetch(`${API}/api/v1/products`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic: value }) });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || "Falha ao criar produto");
      setTopic(""); setView("Produtos"); await refresh();
    } catch (e) { setNotice(e.message); }
  }

  async function sendChat(e) {
    e.preventDefault(); const text = chatInput.trim(); if (!text) return;
    setChat(x => [...x, { role: "user", text }]); setChatInput("");
    try {
      const r = await fetch(`${API}/api/v1/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) });
      const body = await r.json();
      setChat(x => [...x, { role: "assistant", text: r.ok ? body.response : `Erro do Hermes: ${body.detail || "sem resposta"}` }]);
    } catch { setChat(x => [...x, { role: "assistant", text: "API inacessível neste momento." }]); }
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">H</div><div><strong>HERMES</strong><span>PRO / COMMAND CENTER</span></div></div>
      <div className="live-pill"><i className={online ? "online" : "offline"}></i>{online ? "SISTEMA ONLINE" : "API INDISPONÍVEL"}</div>
      <nav>{nav.map(x => <button key={x} className={view === x ? "selected" : ""} onClick={() => setView(x)}>{x}</button>)}</nav>
      <button onClick={refresh}>↻ Atualizar</button>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="kicker">HERMES PRO</span><h1>{view}</h1></div><span className="api-label"><i className={online ? "online" : "offline"}></i>{online ? "API conectada" : "Aguardando API"}</span></header>
      {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {view === "Início" && <Home products={products} jobs={jobs} go={setView} />}
      {view === "Hermes" && <Chat chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} />}
      {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} submit={createProduct} />}
      {view === "Produtos" && <Products items={products} />}
      {view === "Jobs" && <Jobs items={jobs} />}
      {view === "Agentes" && <Agents />}
    </main>
  </div>;
}

function Home({ products, jobs, go }) { return <section className="page"><div className="hero"><div><span className="kicker violet">LIVE OPS</span><h2>Da ideia ao <em>produto.</em></h2><p>Hermes usa IA, worker e armazenamento para transformar um tema em um produto digital verificável.</p><button className="primary" onClick={() => go("Fábrica")}>＋ Criar ebook</button></div></div><div className="metric-grid"><Metric label="Produtos" value={products.length} /><Metric label="Jobs" value={jobs.length} /><Metric label="Concluídos" value={products.filter(x => x.status === "completed").length} /></div><h3>Pipeline</h3><div className="pipeline"><span>IA</span><i>→</i><span>CONTEÚDO</span><i>→</i><span>QA</span><i>→</i><span>PDF + DOCX</span><i>→</i><span>CAPA</span></div></section> }
function Metric({ label, value }) { return <article className="metric"><span>{label}</span><strong>{value}</strong></article> }
function Chat({ chat, input, setInput, send }) { return <section className="page"><span className="kicker violet">HERMES / IA</span><h2>Converse com Hermes</h2><p>Esta conversa usa o mesmo gateway de IA do backend.</p><div className="chat-window">{chat.length === 0 && <div className="chat-empty"><h3>Hermes está aguardando.</h3><p>Pergunte sobre produção, produtos ou operação.</p></div>}{chat.map((m, i) => <div className={`bubble ${m.role}`} key={i}><b>{m.role === "user" ? "Você" : "Hermes"}</b><p>{m.text}</p></div>)}<form className="chat-form" onSubmit={send}><input value={input} onChange={e => setInput(e.target.value)} placeholder="Fale com Hermes…" maxLength={4000} /><button className="primary">Enviar</button></form></div></section> }
function Factory({ topic, setTopic, submit }) { return <section className="page"><span className="kicker violet">PRODUCT FACTORY</span><h2>Criar ebook</h2><p>O backend gera estratégia, conteúdo, revisão, PDF, DOCX e capa.</p><form className="factory-form" onSubmit={submit}><textarea value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: Como ganhar dinheiro com IA para pequenos negócios" required minLength={3} /><button className="primary">Iniciar produção</button></form></section> }
function Products({ items }) { return <section className="page"><span className="kicker violet">CATÁLOGO</span><h2>Seus produtos</h2>{items.length === 0 && <p>Nenhum produto.</p>}<div className="product-grid">{items.map(p => <ProductCard key={p.id} product={p} />)}</div></section> }
function ProductCard({ product }) { const m = product.metadata || {}; const title = product.title || product.topic; return <article className="product-card detailed"><div className="cover-box">{m.cover_url ? <img src={m.cover_url} alt={`Capa de ${title}`} /> : <div><b>H</b><small>{product.current_stage || product.status}</small></div>}</div><div className="product-info"><span className="tag">EBOOK</span><h4>{title}</h4><p>{product.topic}</p><p>Etapa: <strong>{product.current_stage}</strong> · Status: <strong>{product.status}</strong></p>{m.quality_score && <p>Qualidade: {m.quality_score}/100</p>}<div className="asset-actions">{m.pdf_url && <a href={m.pdf_url} target="_blank" rel="noreferrer">Ler PDF</a>}{m.document_url && <a href={m.document_url} target="_blank" rel="noreferrer">Abrir DOCX</a>}{m.cover_url && <a href={m.cover_url} target="_blank" rel="noreferrer">Ver capa</a>}</div></div></article> }
function Jobs({ items }) { return <section className="page"><span className="kicker violet">ORCHESTRATION</span><h2>Jobs</h2>{items.map(j => <article className="job" key={j.id}><strong>{j.job_type}</strong><span>{j.status}</span><small>{j.attempts}/{j.max_attempts}</small>{j.error_message && <p>{j.error_message}</p>}</article>)}</section> }
function Agents() { return <section className="page"><span className="kicker violet">AGENT SYSTEM</span><h2>Agentes</h2><div className="agent-grid">{["RADAR","STRATEGIST","WRITER","EDITOR","DESIGNER","PUBLISHER","GUARDIAN"].map(x => <article className="agent" key={x}><strong>{x}</strong><span>standby até existir execução real</span></article>)}</div></section> }

createRoot(document.getElementById("root")).render(<App />);
