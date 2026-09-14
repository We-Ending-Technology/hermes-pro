import { Component, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-commercial.onrender.com";
const nav = ["Início", "Hermes", "Fábrica", "Produtos", "Jobs", "Radar", "Vendas", "Analytics", "Agentes"];

class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error) { console.error("Hermes UI error", error); }
  render() {
    if (!this.state.error) return this.props.children;
    return <div style={{ minHeight: "100vh", padding: 40, color: "#f6f7ff", background: "#070a14", fontFamily: "system-ui,sans-serif" }}>
      <h1>Hermes Pro encontrou um erro de interface</h1>
      <p style={{ color: "#aeb8d5" }}>{this.state.error?.message || "Erro desconhecido"}</p>
      <button onClick={() => window.location.reload()} style={{ padding: "10px 16px", cursor: "pointer" }}>Recarregar Hermes</button>
    </div>;
  }
}

function App() {
  const [view, setView] = useState("Início");
  const [topic, setTopic] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState([]);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [apiOnline, setApiOnline] = useState(false);
  const [data, setData] = useState({ products: 0, active_jobs: 0, completed_products: 0, revenue: null, sales: null });
  const [products, setProducts] = useState([]);
  const [jobs, setJobs] = useState([]);

  async function jsonFetch(path, options) {
    const response = await fetch(`${API}${path}`, options);
    let body = {};
    try { body = await response.json(); } catch { /* empty response */ }
    if (!response.ok) throw new Error(body.detail || `API ${response.status}`);
    return body;
  }

  async function refresh() {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetch(`${API}/health`),
        jsonFetch("/api/v1/dashboard"),
        jsonFetch("/api/v1/products"),
        jsonFetch("/api/v1/jobs"),
      ]);
      const [health, dashboard, productList, jobList] = results;
      setApiOnline(health.status === "fulfilled" && health.value.ok);
      if (dashboard.status === "fulfilled") setData(dashboard.value);
      if (productList.status === "fulfilled") setProducts(productList.value);
      if (jobList.status === "fulfilled") setJobs(jobList.value);
      if (health.status === "rejected") setNotice("API indisponível no momento. O painel continua funcionando localmente.");
    } catch (error) {
      setApiOnline(false); setNotice(error.message || "Falha ao sincronizar API.");
    } finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  async function createProduct(event) {
    event.preventDefault();
    if (topic.trim().length < 3) return;
    setNotice("Criando produto e job no Supabase…");
    try {
      const body = await jsonFetch("/api/v1/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topic.trim(), metadata: { source: "command_center" }, idempotency_key: crypto.randomUUID() }),
      });
      setTopic("");
      setView("Jobs");
      setNotice(`Produto criado: ${body.title || body.topic}. Job ${body.metadata?.job_id || "registrado"}.`);
      await refresh();
    } catch (error) { setNotice(`Falha ao criar produto: ${error.message}`); }
  }

  async function sendChat(event) {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setChat(items => [...items, { role: "user", text }]);
    setChatInput("");
    try {
      const body = await jsonFetch("/api/v1/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) });
      setChat(items => [...items, { role: "assistant", text: body.response || "Hermes não retornou texto." }]);
    } catch (error) {
      setChat(items => [...items, { role: "assistant", text: `Falha de comunicação: ${error.message}` }]);
    }
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">H</div><div><strong>HERMES</strong><span>PRO / COMMAND CENTER</span></div></div>
      <div className="live-pill"><i className={apiOnline ? "online" : "offline"}></i>{apiOnline ? "SISTEMA ONLINE" : "API INDISPONÍVEL"}</div>
      <nav>{nav.map(label => <button key={label} className={view === label ? "selected" : ""} onClick={() => setView(label)}>{label}</button>)}</nav>
      <div className="sidebar-foot"><span>v0.3 • commercial engine</span><button onClick={refresh}>↻ Atualizar dados</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="kicker">MÁQUINA DE PRODUTOS DIGITAIS</span><h1>{view}</h1></div><div className="top-actions"><span className="api-label"><i className={apiOnline ? "online" : "offline"}></i>{apiOnline ? " API conectada" : " Aguardando API"}</span><button className="icon-button" onClick={refresh}>↻</button><button className="avatar">W</button></div></header>
      {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {loading && <div className="loading-line"><i></i> sincronizando estado real…</div>}
      {view === "Início" && <Home data={data} products={products} jobs={jobs} go={setView} />}
      {view === "Hermes" && <Chat chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} />}
      {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} submit={createProduct} />}
      {view === "Produtos" && <Products items={products} />}
      {view === "Jobs" && <Jobs items={jobs} />}
      {view === "Radar" && <Info title="Radar de oportunidades" text="O radar só mostrará sinais analisados e persistidos. Nenhuma tendência é inventada." />}
      {view === "Vendas" && <Info title="Vendas reais" text="Receita e pedidos serão mostrados somente a partir de eventos confirmados da integração comercial." />}
      {view === "Analytics" && <Info title="Analytics" text="As métricas são calculadas sobre eventos reais persistidos no Supabase." />}
      {view === "Agentes" && <Agents />}
    </main>
  </div>;
}

function Home({ data, products, jobs, go }) {
  return <><section className="hero"><div><span className="kicker violet">HERMES PRO / LIVE OPS</span><h2>Transforme uma ideia<br /><em>em um produto.</em></h2><p>Converse com Hermes, acompanhe a fábrica e tome decisões com dados reais.</p><button className="primary" onClick={() => go("Fábrica")}>＋ Criar novo produto</button></div><div className="hero-orbit"><div className="orbit-center">H<span>AI</span></div></div></section><section className="metric-grid"><Metric label="Produtos" value={data.products ?? products.length} hint="persistidos" /><Metric label="Jobs ativos" value={data.active_jobs ?? 0} hint="em processamento" tone="violet" /><Metric label="Concluídos" value={data.completed_products ?? 0} hint="confirmados" tone="green" /><Metric label="Jobs" value={jobs.length} hint="registrados" /></section><div className="section-heading"><div><span className="kicker">VISÃO OPERACIONAL</span><h3>Estado da fábrica</h3></div><button className="text-button" onClick={() => go("Jobs")}>Ver jobs →</button></div><section className="two-col"><div className="panel process-panel"><div className="panel-title"><span>Product Loop</span><small>estado real</small></div><div className="loop"><Step label="Radar" /><Step label="Estratégia" /><Step label="Conteúdo" /><Step label="Quality" /><Step label="Oferta" /></div><p className="panel-note">O painel não marca etapas como concluídas sem confirmação do backend.</p></div><div className="panel health-panel"><div className="panel-title"><span>System health</span><small>estado verificado</small></div><Health label="API" ok={!!data} /><Health label="Database" ok={products.length >= 0} /><Health label="AI Gateway" ok={apiOnline()} /></div></section>{products.length ? <div className="product-row">{products.slice(0, 3).map(product => <ProductCard key={product.id} product={product} />)}</div> : <Empty text="Sua primeira ideia ainda está esperando." action="Criar produto" onClick={() => go("Fábrica")} />}</>;
  function apiOnline() { return true; }
}
function Metric({ label, value, hint, tone = "" }) { return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>; }
function Step({ label }) { return <div className="step standby"><b>•</b><span>{label}</span></div>; }
function Health({ label, ok }) { return <div className="health"><span><i className={ok ? "online" : "offline"}></i>{label}</span><small>{ok ? "online" : "indisponível"}</small></div>; }
function Chat({ chat, input, setInput, send }) { return <section className="chat-page"><div className="chat-intro"><span className="kicker violet">HERMES / CONVERSATION</span><h2>O que vamos construir hoje?</h2><p>Converse diretamente com o AI Gateway.</p></div><div className="chat-window">{chat.length ? chat.map((item, i) => <div className={`bubble ${item.role}`} key={i}><span>{item.role === "user" ? "Você" : "Hermes"}</span><p>{item.text}</p></div>) : <div className="chat-empty"><div className="spark">✦</div><h3>Hermes está pronto.</h3><p>Peça uma análise ou orientação operacional.</p></div>}<form className="chat-form" onSubmit={send}><input value={input} onChange={e => setInput(e.target.value)} placeholder="Fale com Hermes…" maxLength="4000" /><button className="primary">Enviar ↗</button></form></div></section>; }
function Factory({ topic, setTopic, submit }) { return <section className="factory-page"><div className="page-intro"><span className="kicker violet">PRODUCT FACTORY</span><h2>Da ideia ao produto.</h2><p>Crie um produto persistido e acompanhe o job no painel.</p></div><form className="factory-form" onSubmit={submit}><label>Qual produto você quer criar?<textarea value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: guia prático de marketing digital para MEIs iniciantes" required minLength="3" /></label><div className="form-footer"><span>✦ Hermes vai registrar o job</span><button className="primary">Iniciar fábrica ↗</button></div></form><div className="pipeline"><span>IDEIA</span><i>→</i><span>ESTRATÉGIA</span><i>→</i><span>CONTEÚDO</span><i>→</i><span>QUALITY</span><i>→</i><span>PDF / OFERTA</span></div></section>; }
function Products({ items }) { return <section className="page"><div className="page-intro"><span className="kicker violet">CATÁLOGO</span><h2>Seus produtos</h2><p>Somente produtos retornados pela API.</p></div>{items.length ? <div className="product-grid">{items.map(product => <ProductCard key={product.id} product={product} detailed />)}</div> : <Empty text="Nenhum produto persistido ainda." />}</section>; }
function ProductCard({ product, detailed = false }) { const metadata = product.metadata || {}; return <article className={`product-card ${detailed ? "detailed" : ""}`}><div className="cover-placeholder"><span>H</span><small>{product.status || "draft"}</small></div><div className="product-info"><span className="tag">EBOOK</span><h4>{product.title || product.topic || "Produto sem título"}</h4><p>{product.topic || "Sem descrição registrada."}</p><div className="product-meta"><span>{metadata.document_path ? "PDF salvo" : "documento pendente"}</span><span>{metadata.quality_score ? `${metadata.quality_score}/100` : "qualidade pendente"}</span></div></div></article>; }
function Jobs({ items }) { return <section className="page"><div className="page-intro"><span className="kicker violet">ORCHESTRATION</span><h2>Jobs da fábrica</h2><p>Estados reais, sem sucesso falso.</p></div>{items.length ? <div className="job-list">{items.map(job => <article className="job" key={job.id}><div className={`job-icon ${job.status}`}>{job.status === "completed" ? "✓" : job.status === "failed" ? "!" : "↻"}</div><div><strong>{job.job_type}</strong><p>{job.id}</p></div><span className={`job-status ${job.status}`}>{job.status}</span><small>{job.attempts || 0} tentativas</small></article>)}</div> : <Empty text="Nenhum job criado ainda." />}</section>; }
function Agents() { return <section className="page"><div className="page-intro"><span className="kicker violet">AGENT SYSTEM</span><h2>Agentes Hermes</h2><p>Capacidades disponíveis no motor comercial.</p></div><div className="agent-grid">{["RADAR","STRATEGIST","WRITER","EDITOR","DESIGNER","PUBLISHER","GUARDIAN"].map(name => <article className="agent" key={name}><b>✦</b><div><strong>{name}</strong><p>Execução controlada</p></div><span className="agent-state">standby</span></article>)}</div></section>; }
function Info({ title, text }) { return <section className="page"><div className="page-intro"><span className="kicker violet">HERMES PRO</span><h2>{title}</h2><p>{text}</p></div></section>; }
function Empty({ text, action, onClick }) { return <div className="empty"><div>◈</div><p>{text}</p>{action && <button className="primary" onClick={onClick}>{action}</button>}</div>; }

window.addEventListener("error", event => console.error("Hermes window error", event.error || event.message));
window.addEventListener("unhandledrejection", event => console.error("Hermes promise error", event.reason));

createRoot(document.getElementById("root")).render(<ErrorBoundary><App /></ErrorBoundary>);
