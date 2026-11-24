import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { call, diagnose } from "./api.js";
import "./style.css";
import "./diagnostics.css";
import LowTicketFactory from "./views/LowTicketFactory.jsx";

const NAV = [
  ["⌂", "Início"], ["✦", "Hermes"], ["⌁", "Radar"], ["⚗", "Fábrica"], ["◈", "Produtos"],
  ["▣", "Studio"], ["↗", "Publicação"], ["$", "Vendas"], ["◌", "Analytics"], ["◇", "Experimentos"], ["$", "Low-Ticket"],
  ["◎", "Agentes"], ["⟳", "Automação"], ["⌘", "Integrações"], ["≡", "Logs"], ["?", "Guias"], ["▤", "Jobs"]
];

const DEFAULT_RADAR = { demand: 80, competition: 45, differentiation: 75, production_difficulty: 35, pricing_potential: 70, audience_clarity: 85 };

function App() {
  const [view, setView] = useState("Início");

  const [products, setProducts] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [agentStatus, setAgentStatus] = useState(null);
  const [dashboard, setDashboard] = useState({});
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState("");
  const [online, setOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [diagnostics, setDiagnostics] = useState(null);
  const [topic, setTopic] = useState("");
  const [chat, setChat] = useState(() => { try { return JSON.parse(localStorage.getItem("wet-hermes-chat") || "[]"); } catch { return []; } });
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [radar, setRadar] = useState(null);
  const [sales, setSales] = useState(null);
  const [analytics, setAnalytics] = useState(null);

  const refresh = async () => {
    setBusy(true);
    const health = await safeCall("/health");
    setOnline(Boolean(health?.status === "ok"));
    const results = await Promise.all([
      safeCall("/api/v1/dashboard"), safeCall("/api/v1/products"), safeCall("/api/v1/jobs"), safeCall("/api/v1/integrations"), safeCall("/api/v1/agents/status")
    ]);
    if (results[0]) setDashboard(results[0]);
    if (Array.isArray(results[1])) setProducts(results[1]);
    if (Array.isArray(results[2])) setJobs(results[2]);
    if (Array.isArray(results[3])) setIntegrations(results[3]);
    if (results[4]) setAgentStatus(results[4]);
    setBusy(false);
  };

  const safeCall = async (path, options) => {
    try { return await call(path, options); }
    catch (error) { if (path === "/health") setNotice(error.message); return null; }
  };



  useEffect(() => {
    void refresh();
    const timer = setInterval(() => { void refresh(); }, 30000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { try { localStorage.setItem("wet-hermes-chat", JSON.stringify(chat.slice(-80))); } catch {} }, [chat]);\n\n  const logout = () => setView("Início");

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
      method: "POST",
      body: JSON.stringify({
        topic: topic.trim(),
        metadata: { manual_market_override: true }
      })
    }), "Produto criado e colocado na fila real. A demanda de mercado ficará identificada como não validada.");
    if (product) { setSelected(product); setTopic(""); setView("Jobs"); }
  };

  const sendChat = async (event) => {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text || chatSending) return;
    const nextHistory = [...chat, { role: "user", text }].slice(-10);
    setChat(nextHistory);
    setChatInput("");
    setChatSending(true);
    const conversation = nextHistory
      .map(item => `${item.role === "user" ? "Usuário" : "Hermes"}: ${item.text}`)
      .join("\n")
      .slice(-3800);
    try {
      const result = await call("/api/v1/chat", {
        method: "POST",
        body: JSON.stringify({ message: conversation })
      });
      setChat(items => [...items, {
        role: "assistant",
        text: result.response,
        meta: `${result.provider || "IA"} · ${result.model || "modelo"}`
      }]);
    } catch (error) {
      const detail = error?.message || "Falha de comunicação com o backend.";
      const blocked = error?.status === 402;
      setChat(items => [...items, {
        role: "assistant",
        text: blocked
          ? `O chat chegou ao backend, mas a proteção de orçamento bloqueou a chamada externa de IA. Nenhum consumo foi autorizado. Detalhe: ${detail}`
          : `Não consegui concluir sua mensagem. ${detail} Verifique a conexão e tente novamente.`,
        meta: blocked ? "MODO SEM GASTOS · IA BLOQUEADA" : "FALHA DE CONEXÃO"
      }]);
    } finally {
      setChatSending(false);
    }
  };

  const runDiagnostics = async () => setDiagnostics(await diagnose());
  const selectProduct = product => { setSelected(product); setView("Studio"); };
  const loadSales = () => action(() => call("/api/v1/sales"), "Vendas atualizadas.").then(setSales);
  const loadAnalytics = () => action(() => call("/api/v1/analytics"), "Analytics atualizado.").then(setAnalytics);



  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">W</div><div className="brand-name"><strong>WET</strong><strong>FUTURE LUXURY</strong><span>DIGITAL INTELLIGENCE</span></div></div>
      <div className="live-pill"><i className={online ? "online" : "offline"}></i>{online ? "SISTEMA ONLINE" : "API OFFLINE"}</div>
      <nav>{NAV.map(([icon, label]) => <button key={label} className={view === label ? "selected" : ""} onClick={() => setView(label)}><b>{icon}</b>{label}</button>)}</nav>
      <div className="sidebar-foot"><span>LIVE OPS • REAL DATA</span><button onClick={refresh}>↻ Atualizar</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="kicker">WET / FUTURE LUXURY / DIGITAL INTELLIGENCE</span><h1>{view}</h1></div><div className="top-actions"><span className="api-label"><i className={online ? "online" : "offline"}></i>{online ? "BACKEND CONECTADO" : "BACKEND INDISPONÍVEL"}</span><button className="icon-button" title="Diagnóstico" onClick={runDiagnostics}>⌁</button><button className="icon-button" title="Atualizar dados" onClick={refresh}>↻</button><button className="primary top-mission" onClick={() => setView("Agentes")}>＋ Nova missão</button><button className="avatar" title="WET">W</button></div></header>
      {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {busy && <div className="loading-line"><i /> sincronizando dados reais…</div>}
      {view === "Início" && <Home dashboard={dashboard} products={products} jobs={jobs} agentStatus={agentStatus} online={online} go={setView} select={selectProduct} diagnostics={diagnostics} runDiagnostics={runDiagnostics} />}
      {view === "Hermes" && <ChatView chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} sending={chatSending} />}
      {view === "Radar" && <RadarView data={radar} run={() => action(() => call("/api/v1/radar", { method: "POST", body: JSON.stringify(DEFAULT_RADAR) }), "Radar analisado.").then(setRadar)} />}
      {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} submit={createProduct} products={products} action={action} /> }
      {view === "Produtos" && <Products items={products} select={selectProduct} />}
      {view === "Jobs" && <Jobs jobs={jobs} products={products} action={action} />}
      {view === "Studio" && <Studio product={selected || products[0]} notify={setNotice} refresh={refresh} />}
      {view === "Publicação" && <Publish product={selected || products[0]} integrations={integrations} refresh={refresh} notify={setNotice} />}
      {view === "Vendas" && <SalesView data={sales} load={loadSales} />}
      {view === "Analytics" && <AnalyticsView data={analytics} load={loadAnalytics} />}
      {view === "Experimentos" && <Experiments products={products} radar={radar} />}
      {view === "Low-Ticket" && <LowTicketFactory />}
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

function Home({ dashboard, products, jobs, agentStatus, online, go, select, diagnostics, runDiagnostics }) {
  const activeJobs = jobs.filter(j => ["pending", "running", "retrying"].includes(j.status));
  const completedJobs = jobs.filter(j => j.status === "completed");
  const agents = agentStatus?.agents || [];
  const recentJobs = [...jobs].sort((a,b) => new Date(b.created_at || 0)-new Date(a.created_at || 0)).slice(0,4);
  const metricValue = value => value === null || value === undefined ? "—" : value;
  return <Page title="Command Center" sub="THE FUTURE IS ENGINEERED. · INTELIGÊNCIA PRIVADA EM OPERAÇÃO">
    <section className="hero wet-hero">
      <div className="hero-copy">
        <K>PRIVATE INTELLIGENCE SYSTEM · WET</K>
        <h2>O futuro não se espera.<br/><em>É construído.</em></h2>
        <p>Um centro de comando privado para coordenar inteligência, agentes e operações digitais com precisão. Tudo conectado a dados reais, com autonomia controlada.</p>
        <div className="hero-actions"><Button primary onClick={() => go("Hermes")}>Conversar com Hermes <span>↗</span></Button><Button onClick={() => go("Agentes")}>Ver equipe de agentes</Button></div>
      </div>
      <div className="wet-orbit-scene" aria-hidden="true"><div className="orbit-ring ring-a"/><div className="orbit-ring ring-b"/><div className="orbit-ring ring-c"/><div className="orbit-core"><b>WET</b><small>INTELLIGENCE</small></div><i className="orbit-satellite sat-a"/><i className="orbit-satellite sat-b"/><i className="orbit-satellite sat-c"/></div>
      <div className="hero-foot"><span>PRIVATE ENVIRONMENT</span><span>LIVE OPERATIONS · {online ? "CONNECTED" : "CONNECTION PENDING"}</span></div>
    </section>
    <div className="command-overview">
      <div className="overview-heading"><div><K>OPERAÇÃO</K><h3>Visão executiva</h3></div><span>ATUALIZAÇÃO AUTOMÁTICA · 30S</span></div>
      <div className="metric-grid premium-metrics">
        <Metric label="Produtos no catálogo" value={metricValue(dashboard.products)} />
        <Metric label="Operações em curso" value={activeJobs.length} />
        <Metric label="Produções concluídas" value={metricValue(dashboard.completed_products ?? completedJobs.length)} />
        <Metric label="Vendas confirmadas" value={metricValue(dashboard.sales)} />
      </div>
    </div>
    <div className="home-grid">
      <section className="panel orchestration-panel">
        <div className="section-heading"><div><K>ORQUESTRAÇÃO</K><h3>Equipe de inteligência</h3></div><Button onClick={() => go("Agentes")}>Abrir equipe ↗</Button></div>
        <div className="chief-node"><span className="chief-emblem">✦</span><div><strong>HERMES CHEFE</strong><small>ORQUESTRADOR CENTRAL</small></div><span className={agentStatus?.chief === "ready" ? "state-chip state-ready" : "state-chip"}>{agentStatus?.chief || "Aguardando diagnóstico"}</span></div>
        <div className="agent-constellation">{(agents.length ? agents.slice(0,6) : [{name:"Radar",role:"Pesquisa"},{name:"Analista",role:"Dados"},{name:"Executor",role:"Operações"},{name:"Fábrica",role:"Criação"},{name:"Auditor",role:"Qualidade"},{name:"Sentinela",role:"Monitoramento"}]).map((a,i)=><div className="constellation-agent" key={a.name}><i className={a.status === "ready" ? "agent-dot ready" : "agent-dot"}/><span>{a.name.replace(/^Hermes\s+/,"")}</span><small>{a.role || "Especialista"}</small></div>)}</div>
        <p className="panel-note">{agentStatus?.dispatch_ready ? "O Chefe está liberado para receber missões." : "A equipe está visível; despacho depende das verificações de provedor, orçamento, fila e worker."}</p>
      </section>
      <section className="panel system-panel">
        <div className="section-heading"><div><K>INFRAESTRUTURA</K><h3>Saúde do sistema</h3></div><Button onClick={runDiagnostics}>Diagnosticar</Button></div>
        <div className="system-state"><i className={online ? "online" : "offline"}/><div><strong>{online ? "API respondendo" : "API indisponível"}</strong><small>{online ? "Endpoint de saúde respondeu" : "Aguardando conexão com o backend"}</small></div></div>
        <div className="system-state"><i className={agentStatus?.ai_provider_status === "ready" ? "online" : "offline"}/><div><strong>Provedor de IA</strong><small>{agentStatus?.ai_provider_status || "Não verificado"} · {agentStatus?.ai_provider || "provedor não identificado"}</small></div></div>
        <div className="system-state"><i className={agentStatus?.queue_status === "ready" ? "online" : "offline"}/><div><strong>Fila de execução</strong><small>{agentStatus?.queue_status || "Não verificada"}</small></div></div>
        <div className="system-state"><i className={agentStatus?.worker_status === "ready" ? "online" : "offline"}/><div><strong>Worker</strong><small>{agentStatus?.worker_status || "Não verificado"}</small></div></div>
      </section>
    </div>
    <div className="home-grid home-grid-lower">
      <section className="panel activity-panel">
        <div className="section-heading"><div><K>ATIVIDADE RECENTE</K><h3>Operações</h3></div><Button onClick={() => go("Jobs")}>Todos os jobs ↗</Button></div>
        {recentJobs.length ? <div className="activity-list">{recentJobs.map(job=><div className="activity-row" key={job.id}><i className={job.status === "completed" ? "activity-dot done" : "activity-dot"}/><div><strong>{job.job_type || "Operação"}</strong><small>{job.error_message || job.id}</small></div><span>{job.status}</span></div>)}</div> : <div className="quiet-empty">Nenhuma operação registrada ainda.</div>}
      </section>
      <section className="panel catalog-panel">
        <div className="section-heading"><div><K>PRODUTOS</K><h3>Esteira digital</h3></div><Button onClick={() => go("Produtos")}>Catálogo ↗</Button></div>
        <div className="catalog-summary"><strong>{products.length.toString().padStart(2,"0")}</strong><span>produtos registrados</span></div>
        <div className="catalog-stages"><span>IDEIA</span><span>PRODUÇÃO</span><span>REVISÃO</span><span>PUBLICAÇÃO</span></div>
        {products.slice(0,2).map(p=><button className="mini-product" key={p.id} onClick={() => select(p)}><span>{p.title || p.topic}</span><small>{p.status} · {p.current_stage}</small><b>↗</b></button>)}
        {!products.length && <div className="quiet-empty">Nenhum produto cadastrado.</div>}
      </section>
    </div>
    <div className="section-heading home-section-heading"><div><K>DIAGNÓSTICO DETALHADO</K><h3>Conectividade e dependências</h3></div><Button onClick={runDiagnostics}>Atualizar diagnóstico</Button></div>
    <DiagnosticsPanel data={diagnostics} />
  </Page>;
}
function Metric({ label, value }) { return <article className="metric"><span>{label}</span><strong>{value}</strong><small>valor recebido do sistema</small></article>; }
function Factory({ topic, setTopic, submit, products = [], action }) {
  const [coverProductId, setCoverProductId] = useState("");
  const coverProduct = products.find(item => item.id === coverProductId) || products.find(item => item.metadata?.content_data && !item.metadata?.artifact_paths?.cover);
  const coverUrl = coverProduct?.metadata?.artifacts?.cover || coverProduct?.metadata?.cover_url;
  const hasCoverPath = Boolean(coverProduct?.metadata?.artifact_paths?.cover?.path);
  const generateCover = () => coverProduct && action(() => call(`/api/v1/products/${coverProduct.id}/cover${hasCoverPath ? "?force=true" : ""}`, { method: "POST" }), "Agente de Capas: arquivo gerado, validado e salvo no armazenamento.");
  return <Page title="Fábrica" sub="Produção editorial, capas e validação comercial com orçamento zero.">
    <form className="factory-form" onSubmit={submit}><label>Tema do produto<textarea value={topic} onChange={e => setTopic(e.target.value)} minLength="3" required placeholder="Ex.: guia de marketing digital para MEIs" /></label><div className="form-footer"><span>Conteúdo → revisão → capa → PDF/DOCX → auditoria</span><Button primary type="submit">Iniciar produção ↗</Button></div></form>
    <div className="pipeline">{["IDEIA", "ESTRATÉGIA", "CONTEÚDO", "REVISÃO", "CAPA", "PDF/DOCX", "AUDITORIA"].map((x, i) => <span key={x}>{i ? "→ " : ""}{x}</span>)}</div>
    <section className="panel" style={{ marginTop: 20 }}><span className="kicker">AGENTE DE CAPAS · GRATUITO</span><h3>Gerar e validar capa do ebook</h3><p>Usa somente os provedores gratuitos configurados (OVHcloud ou AI Horde). A capa é salva no Supabase Storage e validada como PNG vertical de 1200×1800 ou superior.</p>
      <label>Selecionar ebook<select value={coverProduct?.id || coverProductId} onChange={e => setCoverProductId(e.target.value)}><option value="">Escolha um ebook com conteúdo</option>{products.filter(p => p.metadata?.content_data).map(p => <option key={p.id} value={p.id}>{p.title || p.topic}{p.metadata?.artifact_paths?.cover?.path ? " · já tem capa" : " · sem capa"}</option>)}</select></label>
      <div className="form-footer"><span>{coverProduct ? (hasCoverPath ? "Capa registrada — pode regenerar" : "Capa pendente") : "Nenhum ebook com conteúdo disponível"}</span><Button primary onClick={generateCover} disabled={!coverProduct}> {hasCoverPath ? "Regenerar capa" : "Gerar capa"} ↗</Button><Button onClick={() => coverProduct && action(() => call(`/api/v1/products/${coverProduct.id}/rebuild-existing`, { method: "POST" }), "Rebuild do ebook enfileirado sem geração de texto paga.")} disabled={!coverProduct || (coverProduct.metadata?.content_data?.illustrations || []).length < 8}>Reconstruir PDF/DOCX</Button></div>
      {coverUrl && <img src={coverUrl} alt={`Capa de ${coverProduct?.title || coverProduct?.topic}`} style={{ display: "block", width: "min(220px, 100%)", marginTop: 16, borderRadius: 8 }} />}
    </section></Page>;
}
function ProductCard({ p, onClick }) { const cover = p.metadata?.artifacts?.cover || p.metadata?.cover_url; return <article className="product-card detailed" onClick={onClick}><div className="cover-placeholder" style={{ position: "relative", overflow: "hidden", padding: 0 }}>{cover ? <img src={cover} alt={`Capa de ${p.title || p.topic}`} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "6px" }} /> : <span style={{ padding: 10 }}>H</span>}<small style={{ position: "absolute", bottom: 8, left: 8, padding: "3px 5px", borderRadius: 4, background: "rgba(8,12,24,.82)" }}>{p.status}</small></div><div className="product-info"><span className="tag">EBOOK</span><h4>{p.title || p.topic}</h4><p>{p.topic}</p><div className="product-meta"><span>stage: {p.current_stage}</span><span>{p.metadata?.quality_score ? `${p.metadata.quality_score}/100` : "quality —"}</span></div></div></article>; }
function Products({ items, select }) { return <Page title="Produtos" sub="Catálogo persistido no Supabase."><div className="product-grid">{items.length ? items.map(p => <ProductCard key={p.id} p={p} onClick={() => select(p)} />) : <Empty text="Nenhum produto ainda." />}</div></Page>; }
function Jobs({ jobs, products, action }) { const productFor = j => products.find(p => p.metadata?.job_id === j.id); return <Page title="Jobs" sub="Fila real com estado e controles operacionais."><div className="job-list">{jobs.length ? jobs.map(j => { const p = productFor(j); const active = ["pending", "running", "retrying"].includes(j.status); return <article className="job" key={j.id}><div className={`job-icon ${j.status}`}>↻</div><div className="job-main"><strong>{p?.title || p?.topic || j.job_type}</strong><p>{j.error_message || `${j.job_type} • ${j.id}`}</p></div><span className={`job-status ${j.status}`}>{j.status}</span><small>{j.attempts}/{j.max_attempts}</small>{active && p && <div className="job-actions"><Button onClick={() => action(() => call(`/api/v1/products/${p.id}/pause`, { method: "POST" }), "Produção pausada.")}>Pausar</Button><Button onClick={() => action(() => call(`/api/v1/jobs/${j.id}/cancel`, { method: "POST" }), "Job cancelado.")}>Cancelar</Button></div>}{j.status === "paused" && p && <div className="job-actions"><Button primary onClick={() => action(() => call(`/api/v1/products/${p.id}/resume`, { method: "POST" }), "Produção retomada.")}>Retomar</Button></div>}</article>; }) : <Empty text="Nenhum job persistido." />}</div></Page>; }
function Studio({ product, notify, refresh }) {
  const [title, setTitle] = useState(product?.title || "");
  useEffect(() => setTitle(product?.title || ""), [product?.id, product?.title]);
  if (!product) return <Page title="Studio" sub="Selecione um produto no catálogo." />;
  const save = async () => {
    try {
      await call("/api/v1/products/" + product.id, { method: "PATCH", body: JSON.stringify({ title }) });
      notify("Produto atualizado.");
      await refresh();
    } catch (e) { notify(e.message); }
  };
  const storedArtifacts = product.metadata?.artifacts || {};
  const artifactEntries = Object.entries(storedArtifacts).length
    ? Object.entries(storedArtifacts)
    : [
        ["PDF", product.metadata?.pdf_url],
        ["DOCX", product.metadata?.document_url || product.metadata?.docx_url],
        ["Capa", product.metadata?.cover_url],
      ].filter(([, url]) => Boolean(url));
  return <Page title="Studio" sub="Edite o produto e abra os arquivos realmente salvos no armazenamento.">
    <div className="panel">
      <label>Título<input value={title} onChange={e => setTitle(e.target.value)} /></label>
      <p>Status: <b>{product.status}</b> · etapa: <b>{product.current_stage}</b></p>
      <Button primary onClick={save}>Salvar alterações</Button>
    </div>
    <div className="panel">
      <h3>Arquivos do produto</h3>
      {artifactEntries.map(([key, value]) => <p key={key}><b>{key}:</b> <a href={value} target="_blank" rel="noreferrer">abrir arquivo ↗</a></p>)}
      {!artifactEntries.length && <p>Os arquivos aparecerão quando o worker concluir a geração.</p>}
    </div>
  </Page>;
}
function RadarView({ data, run }) { return <Page title="Radar" sub="Análise de oportunidade sem promessa de resultado."><Button primary onClick={run}>Analisar oportunidade</Button>{data && <div className="two-col"><div className="panel"><h3>Score {data.score}/100</h3><p>Confiança {data.confidence}%</p>{Object.entries(data.dimensions || {}).map(([k, v]) => <div className="health" key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><div className="panel"><h3>Findings</h3>{(data.findings || []).map(x => <p key={x}>• {x}</p>)}</div></div>}</Page>; }
function Publish({ product, integrations, refresh, notify }) {
  const getIntegration = name => integrations.find(x => x.name?.toLowerCase().includes(name));
  const kiwify = getIntegration("kiwify");
  const hotmart = getIntegration("hotmart");
  const saved = product?.metadata?.publications?.kiwify || {};
  const isPublishable = ["ready_to_publish", "completed"].includes(product?.status);
  const [productId, setProductId] = useState(saved.product_id || "");
  const [checkoutUrl, setCheckoutUrl] = useState(saved.checkout_url || "");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    const publication = product?.metadata?.publications?.kiwify || {};
    setProductId(publication.product_id || "");
    setCheckoutUrl(publication.checkout_url || "");
  }, [product?.id, product?.metadata?.publications?.kiwify?.product_id, product?.metadata?.publications?.kiwify?.checkout_url]);

  const storedArtifacts = product?.metadata?.artifacts || {};
  const artifactEntries = Object.entries(storedArtifacts).length
    ? Object.entries(storedArtifacts)
    : [
        ["PDF", product?.metadata?.pdf_url],
        ["DOCX", product?.metadata?.document_url || product?.metadata?.docx_url],
        ["Capa", product?.metadata?.cover_url],
      ].filter(([, url]) => Boolean(url));

  const saveCheckout = async event => {
    event.preventDefault();
    if (!product?.id || !checkoutUrl.trim()) return;
    setSaving(true);
    try {
      await call("/api/v1/products/" + product.id + "/publication/kiwify", {
        method: "POST",
        body: JSON.stringify({
          product_id: productId.trim() || null,
          checkout_url: checkoutUrl.trim()
        })
      });
      notify?.("Checkout Kiwify salvo no produto. A URL ainda não foi validada por uma compra real.");
      await refresh?.();
    } catch (error) {
      notify?.(error.message);
    } finally {
      setSaving(false);
    }
  };

  if (!product) return <Page title="Publicação" sub="Selecione um ebook pronto para publicação no catálogo." />;

  return <Page title="Publicação" sub="Associe o checkout real da Kiwify ao ebook pronto.">
    <div className="panel">
      <h3>{product.title || product.topic}</h3>
      <p>Kiwify — webhook: <b>{kiwify?.status === "connected" ? "configurado" : "não configurado"}</b></p>
      <p>Hotmart — webhook: <b>{hotmart?.status || "não verificada"}</b></p>
      <p>Arquivos disponíveis: <b>{artifactEntries.length ? "sim" : "não"}</b></p>
      {artifactEntries.map(([key, value]) => <p key={key}><b>{key}:</b> <a href={value} target="_blank" rel="noreferrer">abrir arquivo ↗</a></p>)}
    </div>
    <form className="factory-form" onSubmit={saveCheckout}>
      <h3>Vincular produto da Kiwify</h3>
      <p>Cadastre primeiro o produto na Kiwify, configure a entrega do PDF e copie o link oficial da aba Links.</p>
      <label>ID do produto (opcional)<input value={productId} onChange={event => setProductId(event.target.value)} placeholder="ID mostrado nos dados do produto" /></label>
      <label>Link de checkout HTTPS<input type="url" required value={checkoutUrl} onChange={event => setCheckoutUrl(event.target.value)} placeholder="https://pay.kiwify.com.br/..." /></label>
      <div className="form-footer">
        <span>Ebook pronto · checkout salvo, ainda não validado por compra</span>
        <Button primary type="submit" disabled={saving || !isPublishable}>{saving ? "Salvando…" : "Salvar checkout"}</Button>
      </div>
      {saved.checkout_url && <p>Checkout registrado: <a href={saved.checkout_url} target="_blank" rel="noreferrer">abrir checkout ↗</a> · <b>não testado</b></p>}
      {!isPublishable && <p>Finalize a geração e a revisão do ebook antes de vincular o checkout.</p>}
    </form>
    <div className="panel">
      <p>O Hermes recebe eventos de venda, reembolso e chargeback da Kiwify. O cadastro, preço e entrega do produto são configurados na conta Kiwify; o Hermes não declara uma venda antes de receber o evento confirmado pela plataforma.</p>
    </div>
  </Page>;
}
function SalesView({ data, load }) {
  const money = value => value == null ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
  return <Page title="Vendas" sub="Receita calculada a partir de eventos reais da Kiwify e Hotmart.">
    <Button primary onClick={load}>Atualizar vendas</Button>
    {data ? <>
      <div className="metric-grid">
        <Metric label="Faturamento (BRL)" value={money(data.revenue)} />
        <Metric label="Pedidos líquidos" value={data.orders ?? "—"} />
        <Metric label="Ticket médio" value={money(data.ticket)} />
        <Metric label="Status" value={data.status || "—"} />
      </div>
      <div className="panel" style={{ marginTop: 14 }}>
        <p>{data.message || "Sem observações."}</p>
        {data.status === "error" && <p role="alert">A consulta falhou. Os valores não foram substituídos por estimativas.</p>}
      </div>
    </> : <Empty text="Clique em atualizar para consultar as vendas reais." />}
  </Page>;
}
function AnalyticsView({ data, load }) { return <Page title="Analytics" sub="Insights calculados a partir dos dados persistidos."><Button primary onClick={load}>Atualizar analytics</Button>{data ? <div className="two-col"><div className="panel"><pre>{JSON.stringify(data, null, 2)}</pre></div></div> : <Empty text="Nenhuma leitura carregada." />}</Page>; }
function ChatView({ chat, input, setInput, send, sending }) { return <Page title="Hermes" sub="Assistente operacional conectado ao AI Gateway. O histórico recente é enviado para manter o contexto da conversa."><div className="panel chat-panel"><div className="chat-history" aria-live="polite">{chat.length ? chat.map((m, i) => <div className={`bubble ${m.role}`} key={i}><span>{m.role === "user" ? "Você" : "Hermes"}</span><p>{m.text}</p>{m.meta && <small>{m.meta}</small>}</div>) : <p>Converse com Hermes sobre o sistema, agentes, produtos e operações. O chat informa claramente quando a IA estiver bloqueada ou indisponível.</p>}{sending && <div className="bubble assistant"><span>Hermes</span><p>Processando sua mensagem…</p></div>}</div><form className="chat-form" onSubmit={send}><input value={input} onChange={e => setInput(e.target.value)} disabled={sending} placeholder="Fale com Hermes…" aria-label="Mensagem para Hermes"/><Button primary type="submit" disabled={sending || !input.trim()}>{sending ? "Enviando…" : "Enviar ↗"}</Button></form></div></Page>; }
function DiagnosticsPanel({ data }) { if (!data) return <Empty text="Diagnóstico ainda não executado." />; return <div className="panel diagnostics-grid">{data.checks.map((x, i) => <div className="diag-row" key={`${x.name}-${i}`}><i className={x.status === "online" || x.status === "ready" ? "online" : "offline"}></i><strong>{x.name}</strong><span>{x.status}</span><small>{x.message || ""}</small></div>)}</div>; }
function Integrations({ items, diagnostics, runDiagnostics }) {
  const [kiwify, setKiwify] = useState(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const testKiwify = async () => {
    setBusy("test");
    setMessage("");
    try {
      const result = await call("/api/v1/kiwify/status");
      setKiwify(result);
      setMessage(result.message || (result.connected ? "Kiwify autenticada." : "Credenciais detectadas; conexão ainda não confirmada."));
    } catch (error) {
      setMessage(error.message);
      setKiwify({ connected: false });
    } finally { setBusy(""); }
  };
  const setupKiwifyWebhook = async () => {
    setBusy("webhook");
    setMessage("");
    try {
      const result = await call("/api/v1/kiwify/webhook/setup", { method: "POST" });
      setMessage(result.message || "Webhook configurado.");
      await testKiwify();
    } catch (error) {
      setMessage(error.message);
    } finally { setBusy(""); }
  };
  return <Page title="Integrações" sub="Teste as conexões reais e configure o recebimento de vendas.">
    <div className="panel">
      <div className="section-heading"><div><K>KIWIFY</K><h3>Conexão comercial</h3></div><strong>{kiwify?.connected ? "Conectada" : kiwify?.configured ? "Credenciais detectadas" : "Aguardando teste"}</strong></div>
      <p>{kiwify?.message || "Teste o OAuth para confirmar que o Hermes consegue consultar o catálogo da sua conta."}</p>
      {kiwify?.connected && <p>Produtos retornados pela API: <b>{kiwify.product_count ?? "consulta concluída"}</b></p>}
      <div className="form-footer">
        <Button primary onClick={testKiwify} disabled={Boolean(busy)}>{busy === "test" ? "Testando…" : "Testar OAuth Kiwify"}</Button>
        <Button onClick={setupKiwifyWebhook} disabled={Boolean(busy) || !kiwify?.connected}>{busy === "webhook" ? "Configurando…" : "Configurar webhook"}</Button>
        <a href="https://dashboard.kiwify.com.br" target="_blank" rel="noreferrer">Abrir painel Kiwify ↗</a>
      </div>
      {message && <p role="status">{message}</p>}
      <small>O webhook é criado uma única vez para evitar duplicatas. A criação do produto, upload do PDF/capa e geração do checkout continuam no painel da Kiwify.</small>
    </div>
    <Button onClick={runDiagnostics}>Testar todas as conexões</Button>
    <DiagnosticsPanel data={diagnostics} />
    <div className="integration-list">{items.length ? items.map(x => <div className="panel" key={x.name}><strong>{x.name}</strong><p>{x.status}</p><small>{x.message}</small></div>) : <Empty text="Nenhuma integração retornada pelo backend." />}</div>
  </Page>;
}
function Experiments({ products, radar }) { return <Page title="Experimentos" sub="Área para comparar temas e resultados reais."><div className="metric-grid"><Metric label="Produtos" value={products.length}/><Metric label="Radar disponível" value={radar ? "sim" : "não"}/></div><Empty text="Os experimentos usam somente produtos e análises persistidos; não há conversões inventadas." /></Page>; }
function Agents() {
  const [status, setStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);

  const load = async () => {
    try {
      const [s, r] = await Promise.all([call("/api/v1/agents/status"), call("/api/v1/agents/runs")]);
      setStatus(s); setRuns(r?.runs || []);
    } catch (_) {}
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);

  const dispatch = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSending(true);
    try {
      await call("/api/v1/agents/dispatch", { method: "POST", body: JSON.stringify({ agent: "Hermes Chefe", input: { prompt } }) });
      setPrompt("");
      await load();
    } finally { setSending(false); }
  };

  return <Page title="Agentes" sub="Hermes Chefe coordena especialistas e executa tarefas em background.">
    <div className="metric-grid">
      <Metric label="Chefe" value={status?.chief || "carregando"} />
      <Metric label="Autonomia" value={status?.autonomy_enabled ? "ON" : "OFF"} />
      <Metric label="Execuções" value={runs.length} />
      <Metric label="Fila" value={runs.filter(r => ["pending","running"].includes(r.status)).length} />
    </div>
    <div className="panel">
      <div className="section-heading"><div><K>EQUIPE</K><h3>Agentes especialistas</h3></div></div>
      <div className="product-row">{(status?.agents || []).map(a => <article className="metric" key={a.name}><span>{a.role}</span><strong>{a.name}</strong><small>{a.status}</small></article>)}</div>
    </div>
    <form className="factory-form" onSubmit={dispatch}>
      <label>Nova missão autônoma<textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Ex.: investigar jobs falhos e me entregar a causa e a próxima ação." /></label>
      <div className="form-footer"><span>Chefe → especialistas → Worker → Supabase</span><Button primary type="submit" disabled={sending}>{sending ? "Enviando…" : "Executar missão ↗"}</Button></div>
    </form>
    <div className="panel"><div className="section-heading"><div><K>HISTÓRICO</K><h3>Execuções</h3></div></div>
      {runs.length ? runs.slice(0,10).map(r => <article className="panel" key={r.id}><div className="list-row"><strong>{r.job_status || r.status}</strong><span>{r.instruction}</span><small>{r.agent} · {r.attempts ?? 0}/{r.max_attempts ?? 3}</small></div>{r.output?.output && <details><summary>Ver síntese do Chefe</summary><p>{r.output.output}</p><details><summary>Análises dos especialistas</summary>{Object.entries(r.output.specialists || {}).map(([name, finding]) => <p key={name}><b>{name}:</b> {finding}</p>)}</details></details>}{r.job_error && <p role="alert">{r.job_error}</p>}</article>) : <Empty text="Nenhuma execução de agente ainda." />}
    </div>
  </Page>;
}
function Automation({ jobs }) { const active = useMemo(() => jobs.filter(j => ["pending", "running", "retrying"].includes(j.status)).length, [jobs]); return <Page title="Automação" sub="Visão operacional da fila e do worker."><div className="metric-grid"><Metric label="Jobs ativos" value={active}/><Metric label="Jobs totais" value={jobs.length}/></div><Empty text="A execução automática ocorre no worker; este painel não finge agendamentos que ainda não existem no backend." /></Page>; }
function Logs({ jobs }) { return <Page title="Logs" sub="Eventos de jobs retornados pelo backend."><div className="job-list">{jobs.map(j => <div className="panel" key={j.id}><strong>{j.status}</strong><p>{j.id}</p><small>{j.error_message || "sem erro"}</small></div>)}</div></Page>; }
function Guides() { return <Page title="Guias" sub="Operação do Hermes Pro."><div className="two-col"><div className="panel"><h3>1. Conexão</h3><p>Vercel hospeda a interface. O backend fica no Render. O cliente usa o proxy Vercel e cai para o Render diretamente quando o proxy falhar.</p></div><div className="panel"><h3>2. Produção</h3><p>Fábrica cria produto e job. Redis entrega ao worker. Gemini produz e revisa conteúdo. Supabase persiste estado e artefatos.</p></div><div className="panel"><h3>3. Kiwify</h3><p>Teste OAuth e configure o webhook em Integrações. A criação do produto, o upload do PDF/capa e o checkout são concluídos no painel Kiwify; depois vincule o checkout na guia Publicação.</p></div><div className="panel"><h3>4. Se estiver offline</h3><p>Abra Integrações e execute o diagnóstico. Se Render estiver offline, o painel mostrará a conexão necessária em vez de um erro NOT_FOUND genérico.</p></div></div></Page>; }

createRoot(document.getElementById("root")).render(<App />);
