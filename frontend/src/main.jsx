import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { call, diagnose } from "./api.js";
import "./style.css";
import "./diagnostics.css";

const NAV = [
  ["⌂", "Início"], ["✦", "Hermes"], ["⌁", "Radar"], ["⚗", "Fábrica"], ["◈", "Produtos"],
  ["▣", "Studio"], ["↗", "Publicação"], ["$", "Vendas"], ["◌", "Analytics"], ["◇", "Experimentos"],
  ["◎", "Agentes"], ["⟳", "Automação"], ["⌘", "Integrações"], ["≡", "Logs"], ["?", "Guias"], ["▤", "Jobs"]
];

const DEFAULT_RADAR = { demand: 80, competition: 45, differentiation: 75, production_difficulty: 35, pricing_potential: 70, audience_clarity: 85 };

function App() {
  const [view, setView] = useState("Início");
  const [products, setProducts] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [dashboard, setDashboard] = useState({});
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState("");
  const [online, setOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [diagnostics, setDiagnostics] = useState(null);
  const [topic, setTopic] = useState("");
  const [chat, setChat] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [radar, setRadar] = useState(null);
  const [sales, setSales] = useState(null);
  const [analytics, setAnalytics] = useState(null);

  const refresh = async () => {
    setBusy(true);
    const health = await safeCall("/health");
    setOnline(Boolean(health?.status === "ok"));
    const results = await Promise.all([
      safeCall("/api/v1/dashboard"), safeCall("/api/v1/products"), safeCall("/api/v1/jobs"), safeCall("/api/v1/integrations")
    ]);
    if (results[0]) setDashboard(results[0]);
    if (Array.isArray(results[1])) setProducts(results[1]);
    if (Array.isArray(results[2])) setJobs(results[2]);
    if (Array.isArray(results[3])) setIntegrations(results[3]);
    setBusy(false);
  };

  const safeCall = async (path, options) => {
    try { return await call(path, options); }
    catch (error) { if (path === "/health") setNotice(error.message); return null; }
  };

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, []);

  const action = async (fn, success = "") => {
    setBusy(true);
    try { const result = await fn(); if (success) setNotice(success); return result; }
    catch (error) { setNotice(error.message); return null; }
    finally { await refresh(); setBusy(false); }
  };

  const createProduct = async (event) => {
    event.preventDefault();
    if (!topic.trim()) return;
    const product = await action(() => call("/api/v1/products", {
      method: "POST", body: JSON.stringify({ topic: topic.trim() })
    }), "Produto criado e colocado na fila real.");
    if (product) { setSelected(product); setTopic(""); setView("Jobs"); }
  };

  const sendChat = async (event) => {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setChat(items => [...items, { role: "user", text }]);
    setChatInput("");
    const result = await action(() => call("/api/v1/chat", {
      method: "POST", body: JSON.stringify({ message: text })
    }));
    if (result) setChat(items => [...items, { role: "assistant", text: result.response, meta: `${result.provider || "AI"} · ${result.model || "modelo"}` }]);
  };

  const runDiagnostics = async () => setDiagnostics(await diagnose());
  const selectProduct = product => { setSelected(product); setView("Studio"); };
  const loadSales = () => action(() => call("/api/v1/sales"), "Vendas atualizadas.").then(setSales);
  const loadAnalytics = () => action(() => call("/api/v1/analytics"), "Analytics atualizado.").then(setAnalytics);

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">H</div><div><strong>HERMES</strong><span>PRO / COMMAND CENTER</span></div></div>
      <div className="live-pill"><i className={online ? "online" : "offline"}></i>{online ? "SISTEMA ONLINE" : "API OFFLINE"}</div>
      <nav>{NAV.map(([icon, label]) => <button key={label} className={view === label ? "selected" : ""} onClick={() => setView(label)}><b>{icon}</b>{label}</button>)}</nav>
      <div className="sidebar-foot"><span>LIVE OPS • REAL DATA</span><button onClick={refresh}>↻ Atualizar</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="kicker">HERMES PRO / MONEY OPERATIONS</span><h1>{view}</h1></div><div className="top-actions"><span className="api-label"><i className={online ? "online" : "offline"}></i>{online ? "Backend conectado" : "Backend indisponível"}</span><button className="icon-button" onClick={runDiagnostics}>⌁</button><button className="icon-button" onClick={refresh}>↻</button><button className="avatar">W</button></div></header>
      {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {busy && <div className="loading-line"><i /> sincronizando dados reais…</div>}
      {view === "Início" && <Home dashboard={dashboard} products={products} jobs={jobs} go={setView} select={selectProduct} diagnostics={diagnostics} runDiagnostics={runDiagnostics} />}
      {view === "Hermes" && <ChatView chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} />}
      {view === "Radar" && <RadarView data={radar} run={() => action(() => call("/api/v1/radar", { method: "POST", body: JSON.stringify(DEFAULT_RADAR) }), "Radar analisado.").then(setRadar)} />}
      {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} submit={createProduct} />}
      {view === "Produtos" && <Products items={products} select={selectProduct} />}
      {view === "Jobs" && <Jobs jobs={jobs} products={products} action={action} />}
      {view === "Studio" && <Studio product={selected || products[0]} notify={setNotice} refresh={refresh} />}
      {view === "Publicação" && <Publish product={selected || products[0]} integrations={integrations} />}
      {view === "Vendas" && <SalesView data={sales} load={loadSales} />}
      {view === "Analytics" && <AnalyticsView data={analytics} load={loadAnalytics} />}
      {view === "Experimentos" && <Experiments products={products} radar={radar} />}
      {view === "Agentes" && <Agents />}
      {view === "Automação" && <Automation jobs={jobs} />}
      {view === "Integrações" && <Integrations items={integrations} diagnostics={diagnostics} runDiagnostics={runDiagnostics} />}
      {view === "Logs" && <Logs jobs={jobs} />}
      {view === "Guias" && <Guides />}
    </main>
  </div>;
}

const K = ({ children }) => <span className="kicker violet">{children}</span>;
const Button = ({ children, onClick, primary = false, type = "button", disabled = false }) => <button type={type} disabled={disabled} className={primary ? "primary" : "text-button"} onClick={onClick}>{children}</button>;
const Page = ({ title, sub, children }) => <section className="page"><div className="page-intro"><K>HERMES PRO</K><h2>{title}</h2><p>{sub}</p></div>{children}</section>;
const Empty = ({ text }) => <div className="panel empty">{text}</div>;

function Home({ dashboard, products, jobs, go, select, diagnostics, runDiagnostics }) {
  return <Page title="Command Center" sub="Operação comercial ligada ao backend real.">
    <section className="hero"><div><K>LIVE PRODUCT ENGINE</K><h2>Ideia → produto → venda.</h2><p>O Hermes não inventa métricas nem estados de publicação.</p><Button primary onClick={() => go("Fábrica")}>＋ Criar produto</Button></div><div className="hero-orbit"><div className="orbit-center">H<span>AI</span></div><div className="orbit-dot dot-one">✦</div><div className="orbit-dot dot-two">↗</div><div className="orbit-dot dot-three">$</div></div></section>
    <div className="metric-grid"><Metric label="Produtos" value={dashboard.products ?? 0}/><Metric label="Jobs ativos" value={dashboard.active_jobs ?? 0}/><Metric label="Concluídos" value={dashboard.completed_products ?? 0}/><Metric label="Vendas" value={dashboard.sales ?? 0}/></div>
    <div className="section-heading"><div><K>SISTEMA</K><h3>Conectividade</h3></div><Button onClick={runDiagnostics}>Diagnosticar agora</Button></div>
    <DiagnosticsPanel data={diagnostics} />
    <div className="section-heading"><div><K>PIPELINE</K><h3>Esteira</h3></div><Button onClick={() => go("Jobs")}>Abrir Jobs →</Button></div>
    <div className="panel process-panel"><div className="loop">{["Radar", "Estratégia", "Conteúdo", "Quality", "Studio", "Oferta", "Hotmart"].map((x, i) => <div className="step" key={x}><b>{i + 1}</b><span>{x}</span></div>)}</div><p className="panel-note">{jobs.length} jobs persistidos.</p></div>
    <div className="section-heading"><div><K>CATÁLOGO</K><h3>Produtos recentes</h3></div><Button onClick={() => go("Produtos")}>Abrir →</Button></div>
    <div className="product-row">{products.slice(0, 3).map(p => <ProductCard key={p.id} p={p} onClick={() => select(p)} />)}</div>
  </Page>;
}
function Metric({ label, value }) { return <article className="metric"><span>{label}</span><strong>{value}</strong><small>estado persistido</small></article>; }
function Factory({ topic, setTopic, submit }) { return <Page title="Fábrica" sub="Digite um tema e crie um job real no servidor."><form className="factory-form" onSubmit={submit}><label>Tema do produto<textarea value={topic} onChange={e => setTopic(e.target.value)} minLength="3" required placeholder="Ex.: guia de marketing digital para MEIs" /></label><div className="form-footer"><span>Render → Redis → Worker → Gemini → Supabase</span><Button primary type="submit">Iniciar produção ↗</Button></div></form><div className="pipeline">{["IDEIA", "ESTRATÉGIA", "CONTEÚDO", "REVISÃO", "STUDIO", "ARTEFATOS"].map((x, i) => <span key={x}>{i ? "→ " : ""}{x}</span>)}</div></Page>; }
function ProductCard({ p, onClick }) { return <article className="product-card detailed" onClick={onClick}><div className="cover-placeholder"><span>H</span><small>{p.status}</small></div><div className="product-info"><span className="tag">EBOOK</span><h4>{p.title || p.topic}</h4><p>{p.topic}</p><div className="product-meta"><span>stage: {p.current_stage}</span><span>{p.metadata?.quality_score ? `${p.metadata.quality_score}/100` : "quality —"}</span></div></div></article>; }
function Products({ items, select }) { return <Page title="Produtos" sub="Catálogo persistido no Supabase."><div className="product-grid">{items.length ? items.map(p => <ProductCard key={p.id} p={p} onClick={() => select(p)} />) : <Empty text="Nenhum produto ainda." />}</div></Page>; }
function Jobs({ jobs, products, action }) { const productFor = j => products.find(p => p.metadata?.job_id === j.id); return <Page title="Jobs" sub="Fila real com estado e controles operacionais."><div className="job-list">{jobs.length ? jobs.map(j => { const p = productFor(j); const active = ["pending", "running", "retrying"].includes(j.status); return <article className="job" key={j.id}><div className={`job-icon ${j.status}`}>↻</div><div className="job-main"><strong>{p?.title || p?.topic || j.job_type}</strong><p>{j.error_message || `${j.job_type} • ${j.id}`}</p></div><span className={`job-status ${j.status}`}>{j.status}</span><small>{j.attempts}/{j.max_attempts}</small>{active && p && <div className="job-actions"><Button onClick={() => action(() => call(`/api/v1/products/${p.id}/pause`, { method: "POST" }), "Produção pausada.")}>Pausar</Button><Button onClick={() => action(() => call(`/api/v1/jobs/${j.id}/cancel`, { method: "POST" }), "Job cancelado.")}>Cancelar</Button></div>}{j.status === "paused" && p && <div className="job-actions"><Button primary onClick={() => action(() => call(`/api/v1/products/${p.id}/resume`, { method: "POST" }), "Produção retomada.")}>Retomar</Button></div>}</article>; }) : <Empty text="Nenhum job persistido." />}</div></Page>; }
function Studio({ product, notify, refresh }) { const [title, setTitle] = useState(product?.title || ""); useEffect(() => setTitle(product?.title || ""), [product?.id, product?.title]); if (!product) return <Page title="Studio" sub="Selecione um produto no catálogo." />; const save = async () => { try { await call(`/api/v1/products/${product.id}`, { method: "PATCH", body: JSON.stringify({ title }) }); notify("Produto atualizado."); await refresh(); } catch (e) { notify(e.message); } }; return <Page title="Studio" sub="Edite o produto e abra os artefatos gerados."><div className="panel"><label>Título<input value={title} onChange={e => setTitle(e.target.value)} /></label><p>Status: <b>{product.status}</b> · etapa: <b>{product.current_stage}</b></p><Button primary onClick={save}>Salvar alterações</Button></div><div className="panel"><h3>Artefatos</h3>{Object.entries(product.metadata?.artifacts || {}).map(([k, v]) => <p key={k}><b>{k}:</b> <a href={v} target="_blank" rel="noreferrer">abrir arquivo</a></p>)}{!Object.keys(product.metadata?.artifacts || {}).length && <p>Os arquivos aparecerão quando o worker concluir a geração.</p>}</div></Page>; }
function RadarView({ data, run }) { return <Page title="Radar" sub="Análise de oportunidade sem promessa de resultado."><Button primary onClick={run}>Analisar oportunidade</Button>{data && <div className="two-col"><div className="panel"><h3>Score {data.score}/100</h3><p>Confiança {data.confidence}%</p>{Object.entries(data.dimensions || {}).map(([k, v]) => <div className="health" key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><div className="panel"><h3>Findings</h3>{(data.findings || []).map(x => <p key={x}>• {x}</p>)}</div></div>}</Page>; }
function Publish({ product, integrations }) { const hotmart = integrations.find(x => x.name?.toLowerCase().includes("hotmart")); return <Page title="Publicação" sub="Preparação comercial e sincronização do catálogo Hotmart."><div className="panel"><h3>{product?.title || product?.topic || "Nenhum produto selecionado"}</h3><p>Hotmart: <b>{hotmart?.status || "não verificada"}</b></p><p>Artefatos: <b>{Object.keys(product?.metadata?.artifacts || {}).length ? "gerados" : "pendentes"}</b></p><p>A API pública da Hotmart permite consultar/sincronizar produtos e ofertas e receber webhooks. A criação de um novo produto digital continua no painel da Hotmart; o Hermes não simula uma publicação que a API não documenta.</p></div></Page>; }
function SalesView({ data, load }) { return <Page title="Vendas" sub="Dados vindos de eventos reais persistidos."><Button primary onClick={load}>Atualizar vendas</Button>{data ? <div className="metric-grid"><Metric label="Receita" value={data.revenue ?? 0}/><Metric label="Pedidos" value={data.orders ?? 0}/><Metric label="Aprovados" value={data.approved ?? 0}/><Metric label="Reembolsos" value={data.refunds ?? 0}/></div> : <Empty text="Clique em atualizar para consultar as vendas reais." />}</Page>; }
function AnalyticsView({ data, load }) { return <Page title="Analytics" sub="Insights calculados a partir dos dados persistidos."><Button primary onClick={load}>Atualizar analytics</Button>{data ? <div className="two-col"><div className="panel"><pre>{JSON.stringify(data, null, 2)}</pre></div></div> : <Empty text="Nenhuma leitura carregada." />}</Page>; }
function ChatView({ chat, input, setInput, send }) { return <Page title="Hermes" sub="Assistente operacional conectado ao AI Gateway."><div className="panel chat-panel"><div className="chat-history">{chat.length ? chat.map((m, i) => <div className={`bubble ${m.role}`} key={i}><span>{m.role === "user" ? "Você" : "Hermes"}</span><p>{m.text}</p>{m.meta && <small>{m.meta}</small>}</div>) : <p>Envie uma instrução. Se o Gemini estiver indisponível, o erro será mostrado claramente.</p>}</div><form className="chat-form" onSubmit={send}><input value={input} onChange={e => setInput(e.target.value)} placeholder="Fale com Hermes…"/><Button primary type="submit">Enviar ↗</Button></form></div></Page>; }
function DiagnosticsPanel({ data }) { if (!data) return <Empty text="Diagnóstico ainda não executado." />; return <div className="panel diagnostics-grid">{data.checks.map((x, i) => <div className="diag-row" key={`${x.name}-${i}`}><i className={x.status === "online" || x.status === "ready" ? "online" : "offline"}></i><strong>{x.name}</strong><span>{x.status}</span><small>{x.message || ""}</small></div>)}</div>; }
function Integrations({ items, diagnostics, runDiagnostics }) { return <Page title="Integrações" sub="Estado das conexões sem expor segredos."><Button primary onClick={runDiagnostics}>Testar conexões</Button><DiagnosticsPanel data={diagnostics} /><div className="integration-list">{items.length ? items.map(x => <div className="panel" key={x.name}><strong>{x.name}</strong><p>{x.status}</p><small>{x.message}</small></div>) : <Empty text="Nenhuma integração retornada pelo backend." />}</div></Page>; }
function Experiments({ products, radar }) { return <Page title="Experimentos" sub="Área para comparar temas e resultados reais."><div className="metric-grid"><Metric label="Produtos" value={products.length}/><Metric label="Radar disponível" value={radar ? "sim" : "não"}/></div><Empty text="Os experimentos usam somente produtos e análises persistidos; não há conversões inventadas." /></Page>; }
function Agents() { return <Page title="Agentes" sub="Agentes operacionais registrados no backend."><AgentList /></Page>; }
function AgentList() { const [items, setItems] = useState([]); const [result, setResult] = useState(null); useEffect(() => { call("/api/v1/agents").then(x => setItems(x?.agents || [])).catch(() => setItems([])); }, []); const run = async agent => { try { setResult(await call("/api/v1/agents/run", { method: "POST", body: JSON.stringify({ agent, input: "diagnóstico operacional do Hermes Pro" }) })); } catch (e) { setResult({ error: e.message }); } }; return <div className="product-grid">{items.map(agent => <div className="panel" key={agent}><h3>{agent}</h3><Button onClick={() => run(agent)}>Executar</Button></div>)}{result && <div className="panel"><pre>{JSON.stringify(result, null, 2)}</pre></div>}</div>; }
function Automation({ jobs }) { const active = useMemo(() => jobs.filter(j => ["pending", "running", "retrying"].includes(j.status)).length, [jobs]); return <Page title="Automação" sub="Visão operacional da fila e do worker."><div className="metric-grid"><Metric label="Jobs ativos" value={active}/><Metric label="Jobs totais" value={jobs.length}/></div><Empty text="A execução automática ocorre no worker; este painel não finge agendamentos que ainda não existem no backend." /></Page>; }
function Logs({ jobs }) { return <Page title="Logs" sub="Eventos de jobs retornados pelo backend."><div className="job-list">{jobs.map(j => <div className="panel" key={j.id}><strong>{j.status}</strong><p>{j.id}</p><small>{j.error_message || "sem erro"}</small></div>)}</div></Page>; }
function Guides() { return <Page title="Guias" sub="Operação do Hermes Pro."><div className="two-col"><div className="panel"><h3>1. Conexão</h3><p>Vercel hospeda a interface. O backend fica no Render. O cliente usa o proxy Vercel e cai para o Render diretamente quando o proxy falhar.</p></div><div className="panel"><h3>2. Produção</h3><p>Fábrica cria produto e job. Redis entrega ao worker. Gemini produz e revisa conteúdo. Supabase persiste estado e artefatos.</p></div><div className="panel"><h3>3. Hotmart</h3><p>O Hermes consulta o catálogo disponível e recebe vendas por webhook. A criação inicial do produto continua no painel Hotmart.</p></div><div className="panel"><h3>4. Se estiver offline</h3><p>Abra Integrações e execute o diagnóstico. Se Render estiver offline, o painel mostrará a conexão necessária em vez de um erro NOT_FOUND genérico.</p></div></div></Page>; }

createRoot(document.getElementById("root")).render(<App />);
