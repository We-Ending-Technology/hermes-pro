import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { call, diagnose, setAdminToken, clearAdminToken, hasAdminToken } from "./api.js";
import "./auth.css";
import "./style.css";
import "./diagnostics.css";

const NAV = [
  ["⌂", "Início"], ["✦", "Hermes"], ["⌁", "Radar"], ["⚗", "Fábrica"], ["◈", "Produtos"],
  ["▣", "Studio"], ["↗", "Publicação"], ["$", "Vendas"], ["◌", "Analytics"], ["◇", "Experimentos"],
["◉", "Canais"], ["◎", "Agentes"], ["⟳", "Automação"], ["⌘", "Integrações"], ["≡", "Logs"], ["?", "Guias"], ["▤", "Jobs"]
];

const DEFAULT_RADAR = { demand: 80, competition: 45, differentiation: 75, production_difficulty: 35, pricing_potential: 70, audience_clarity: 85 };

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [authKey, setAuthKey] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");
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
  const refreshing = useRef(false);
  const chatPending = useRef(false);

  const login = async (event) => {
    event.preventDefault();
    const candidate = authKey.trim();
    if (!candidate) return;
    setAuthBusy(true);
    setAuthError("");
    setAdminToken(candidate);
    try {
      await call("/api/v1/auth/verify");
      setAuthenticated(true);
      setAuthKey("");
    } catch (error) {
      clearAdminToken();
      setAuthError(error.message || "Acesso negado. Confira a chave configurada no Render.");
    } finally {
      setAuthBusy(false);
    }
  };

  const logout = () => {
    clearAdminToken();
    setAuthenticated(false);
    setProducts([]); setJobs([]); setIntegrations([]); setDashboard({});
    setNotice("");
  };

  const refresh = async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    setBusy(true);
    try {
      const health = await safeCall("/");
      setOnline(Boolean(health?.status === "ok"));
      const results = await Promise.all([
        safeCall("/api/v1/dashboard"), safeCall("/api/v1/products"), safeCall("/api/v1/jobs"), safeCall("/api/v1/integrations")
      ]);
      if (results[0]) setDashboard(results[0]);
      if (Array.isArray(results[1])) setProducts(results[1]);
      if (Array.isArray(results[2])) setJobs(results[2]);
      if (Array.isArray(results[3])) setIntegrations(results[3]);
    } finally {
      refreshing.current = false;
      setBusy(false);
    }
  };

  const safeCall = async (path, options) => {
    try { return await call(path, options); }
    catch (error) { if (!hasAdminToken()) setAuthenticated(false); setNotice(error.message); return null; }
  };

  useEffect(() => {
    if (!authenticated) return undefined;
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [authenticated]);

  const action = async (fn, success = "") => {
    setBusy(true);
    try { const result = await fn(); if (success) setNotice(success); return result; }
    catch (error) { if (!hasAdminToken()) setAuthenticated(false); setNotice(error.message); return null; }
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
    if (!text || chatPending.current) return;

    chatPending.current = true;
    setChat(items => [...items, { role: "user", text }]);
    setChatInput("");
    setBusy(true);
    setNotice("Hermes Chefe recebeu a tarefa e está iniciando os agentes.");

    try {
      // Dispatch is persistent: the browser no longer waits for a long synchronous AI response.
      const queued = await call("/api/v1/agents/dispatch", {
        method: "POST",
        body: JSON.stringify({ agent: "Hermes Chefe", input: { prompt: text } }),
        timeoutMs: 20000,
      });
      const runId = queued?.run_id;
      if (!runId) throw new Error("A API não confirmou o ID da execução do Hermes Chefe.");

      let completedRun = null;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        const result = await call("/api/v1/agents/runs", { timeoutMs: 15000 });
        const run = (result.runs || []).find(item => String(item.id) === String(runId));
        if (!run) continue;

        const status = run.job_status || run.status;
        if (status === "completed") {
          completedRun = run;
          break;
        }
        if (status === "failed" || status === "cancelled") {
          throw new Error(run.job_error || run.error_message || `Execução ${status}: ${runId}`);
        }
        if (attempt > 0 && attempt % 10 === 9) {
          setNotice(`Hermes Chefe trabalhando. Tempo decorrido: ${Math.ceil((attempt + 1) * 3 / 60)} min.`);
        }
      }

      if (!completedRun) {
        setChat(items => [...items, {
          role: "assistant",
          text: `A execução continua registrada no servidor e não foi perdida. ID: ${runId}. Consulte a área Jobs para acompanhar o estado.`,
          meta: "Hermes Chefe · execução persistente",
        }]);
        setNotice(`A tarefa continua em execução. ID: ${runId}`);
        return;
      }

      const output = completedRun.output || {};
      const answer = typeof output.output === "string" ? output.output : "";
      if (!answer.trim()) throw new Error("O worker marcou a execução como concluída, mas não entregou uma resposta válida.");
      setChat(items => [...items, {
        role: "assistant",
        text: answer,
        meta: `${output.provider || "Hermes Chefe"} · ${output.model || "time de agentes"}`,
        action: output.action || null,
        evidence: output.operational_context || null,
      }]);
      setNotice("Hermes Chefe concluiu a execução persistente.");
    } catch (error) {
      setChat(items => [...items, {
        role: "assistant",
        text: `Não foi possível concluir a tarefa: ${error.message}`,
        meta: "Hermes Chefe · falha registrada",
      }]);
      setNotice(error.message || "Falha ao executar a tarefa.");
    } finally {
      chatPending.current = false;
      setBusy(false);
      await refresh();
    }
  };

  const runDiagnostics = async () => setDiagnostics(await diagnose());
  const selectProduct = product => { setSelected(product); setView("Studio"); };
  const loadSales = () => action(() => call("/api/v1/sales"), "Vendas atualizadas.").then(setSales);
  const loadAnalytics = () => action(() => call("/api/v1/analytics"), "Analytics atualizado.").then(setAnalytics);

  if (!authenticated) return <AuthGate value={authKey} onChange={setAuthKey} onSubmit={login} busy={authBusy} error={authError} />;

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">H</div><div><strong>HERMES</strong><span>PRO / COMMAND CENTER</span></div></div>
      <div className="live-pill"><i className={online ? "online" : "offline"}></i>{online ? "SISTEMA ONLINE" : "API OFFLINE"}</div>
      <nav>{NAV.map(([icon, label]) => <button key={label} className={view === label ? "selected" : ""} onClick={() => setView(label)}><b>{icon}</b>{label}</button>)}</nav>
      <div className="sidebar-foot"><span>LIVE OPS • REAL DATA</span><button onClick={refresh}>↻ Atualizar</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="kicker">HERMES PRO / MONEY OPERATIONS</span><h1>{view}</h1></div><div className="top-actions"><span className="api-label"><i className={online ? "online" : "offline"}></i>{online ? "Backend conectado" : "Backend indisponível"}</span><button className="icon-button" onClick={runDiagnostics}>⌁</button><button className="icon-button" onClick={refresh}>↻</button><button className="text-button" onClick={logout}>Sair</button><button className="avatar">W</button></div></header>
      {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {busy && <div className="loading-line"><i /> sincronizando dados reais…</div>}
      {view === "Início" && <Home dashboard={dashboard} products={products} jobs={jobs} go={setView} select={selectProduct} diagnostics={diagnostics} runDiagnostics={runDiagnostics} />}
      {view === "Hermes" && <ChatView chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} />}
      {view === "Canais" && <RevenueChannels integrations={integrations} />}
      {view === "Radar" && <RadarView />}
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


function AuthGate({ value, onChange, onSubmit, busy, error }) {
  return <main className="auth-screen">
    <form className="auth-card" onSubmit={onSubmit}>
      <div className="auth-mark">H</div>
      <span className="auth-kicker">HERMES PRO / ACESSO PRIVADO</span>
      <h1>Bem-vindo de volta.</h1>
      <p>Informe a chave privada configurada no serviço de API do Render para abrir seu Command Center.</p>
      <label htmlFor="hermes-access-key">Chave de acesso</label>
      <input id="hermes-access-key" type="password" autoComplete="current-password" value={value} onChange={event => onChange(event.target.value)} placeholder="HERMES_API_KEY" required autoFocus />
      {error && <div className="auth-error" role="alert">{error}</div>}
      <button className="primary auth-submit" type="submit" disabled={busy || !value.trim()}>{busy ? "Validando acesso…" : "Entrar no Hermes"}</button>
      <small>A chave é mantida somente na memória desta aba e não é salva no armazenamento do navegador.</small>
    </form>
  </main>;
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
function ProductCard({ p, onClick }) {
  const cover = p.metadata?.artifacts?.cover || p.metadata?.cover_url;
  return <article className="product-card detailed" onClick={onClick}>
    <div className="cover-placeholder">
      {cover ? <img src={cover} alt={`Capa de ${p.title || p.topic}`} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "12px" }} /> : <span>H</span>}
      <small>{p.status}</small>
    </div>
    <div className="product-info"><span className="tag">EBOOK</span><h4>{p.title || p.topic}</h4><p>{p.topic}</p><div className="product-meta"><span>stage: {p.current_stage}</span><span>{p.metadata?.quality_score ? `${p.metadata.quality_score}/100` : "quality —"}</span></div></div>
  </article>;
}
function Products({ items, select }) { return <Page title="Produtos" sub="Catálogo persistido no Supabase."><div className="product-grid">{items.length ? items.map(p => <ProductCard key={p.id} p={p} onClick={() => select(p)} />) : <Empty text="Nenhum produto ainda." />}</div></Page>; }
function Jobs({ jobs, products, action }) { const productFor = j => products.find(p => p.metadata?.job_id === j.id); return <Page title="Jobs" sub="Fila real com estado e controles operacionais."><div className="job-list">{jobs.length ? jobs.map(j => { const p = productFor(j); const active = ["pending", "running", "retrying"].includes(j.status); return <article className="job" key={j.id}><div className={`job-icon ${j.status}`}>↻</div><div className="job-main"><strong>{p?.title || p?.topic || j.job_type}</strong><p>{j.error_message || `${j.job_type} • ${j.id}`}</p></div><span className={`job-status ${j.status}`}>{j.status}</span><small>{j.attempts}/{j.max_attempts}</small>{active && p && <div className="job-actions"><Button onClick={() => action(() => call(`/api/v1/products/${p.id}/pause`, { method: "POST" }), "Produção pausada.")}>Pausar</Button><Button onClick={() => action(() => call(`/api/v1/jobs/${j.id}/cancel`, { method: "POST" }), "Job cancelado.")}>Cancelar</Button></div>}{j.status === "paused" && p && <div className="job-actions"><Button primary onClick={() => action(() => call(`/api/v1/products/${p.id}/resume`, { method: "POST" }), "Produção retomada.")}>Retomar</Button></div>}</article>; }) : <Empty text="Nenhum job persistido." />}</div></Page>; }
function Studio({ product, notify, refresh }) {
  const [title, setTitle] = useState(product?.title || "");
  const [showReader, setShowReader] = useState(true);
  useEffect(() => { setTitle(product?.title || ""); setShowReader(true); }, [product?.id, product?.title]);
  if (!product) return <Page title="Studio" sub="Selecione um produto no catálogo." />;

  const save = async () => {
    try {
      await call("/api/v1/products/" + product.id, { method: "PATCH", body: JSON.stringify({ title }) });
      notify("Produto atualizado.");
      await refresh();
    } catch (e) { notify(e.message); }
  };

  const rawArtifacts = product.metadata?.artifacts && Object.keys(product.metadata.artifacts).length
    ? product.metadata.artifacts
    : { pdf: product.metadata?.pdf_url, cover: product.metadata?.cover_url, docx: product.metadata?.document_url };
  const artifacts = Object.entries(rawArtifacts).filter(([, value]) => typeof value === "string" && /^https?:\/\//i.test(value));
  const cover = rawArtifacts.cover;
  const pdf = rawArtifacts.pdf;
  const content = product.metadata?.content_data || {};
  const chapters = Array.isArray(content.chapters) ? content.chapters : [];
  const review = product.metadata?.review || {};
  const qualityGate = product.metadata?.quality_gate || {};
  const hasContent = Boolean(content.introduction || chapters.length || content.conclusion);

  return <Page title="Studio" sub="Veja a capa, leia o conteúdo e abra os arquivos reais do produto.">
    <div className="two-col">
      <div className="panel">
        {cover && <img src={cover} alt={`Capa do ebook ${product.title || product.topic}`} style={{ display: "block", width: "min(100%, 300px)", maxHeight: "440px", objectFit: "contain", margin: "0 auto 20px", borderRadius: "12px" }} />}
        {!cover && <div className="panel-note">A capa ainda não foi gerada para este produto.</div>}
        <label>Título<input value={title} onChange={e => setTitle(e.target.value)} /></label>
        <p>Status: <b>{product.status}</b> · etapa: <b>{product.current_stage}</b></p>
        {product.metadata?.quality_score != null && <p>Nota de revisão: <b>{product.metadata.quality_score}/100</b></p>}
        {qualityGate.word_count != null && <p>Extensão: <b>{qualityGate.word_count}</b> palavras · mínimo comercial: <b>{qualityGate.minimums?.total_words || 1800}</b></p>}
        <Button primary onClick={save} disabled={["completed", "cancelled"].includes(product.status)}>Salvar alterações</Button>
      </div>
      <div className="panel">
        <h3>Prévia do PDF</h3>
        {pdf
          ? <iframe title={`Prévia do ebook ${product.title || product.topic}`} src={pdf + "#toolbar=1&navpanes=0"} style={{ width: "100%", height: "620px", border: "1px solid var(--border, #333)", borderRadius: "10px", background: "#fff" }} />
          : <p>O PDF só será criado depois que o conteúdo passar pela revisão de qualidade.</p>}
      </div>
    </div>
    {product.status === "review_required" && <div className="panel">
      <h3>Revisão necessária</h3>
      <p>Este conteúdo não passou pelo critério de qualidade e ainda não pode ser publicado.</p>
      {review.score != null && <p>Nota da revisão editorial: <b>{review.score}/100</b></p>}
      {qualityGate.score != null && <p>Nota determinística: <b>{qualityGate.score}/100</b> · palavras: <b>{qualityGate.word_count || 0}</b></p>}
      {Array.isArray(qualityGate.findings) && qualityGate.findings.length > 0 && <ul>{qualityGate.findings.map((finding, i) => <li key={"gate-" + i}>{finding}</li>)}</ul>}
      {Array.isArray(review.findings) && review.findings.length > 0 && <ul>{review.findings.map((finding, i) => <li key={"review-" + i}>{finding}</li>)}</ul>}
      <p className="panel-note">Este produto está bloqueado para publicação. Arquivos já existentes podem ser consultados, mas não podem ser vinculados a um checkout até a aprovação do quality gate.</p>
    </div>}
    <div className="panel">
      <div className="section-heading"><div><h3>Leitura do ebook</h3><p className="panel-note">{chapters.length} capítulos · conteúdo salvo no Hermes</p></div>
        <Button onClick={() => setShowReader(value => !value)}>{showReader ? "Recolher leitura" : "Ler ebook completo"}</Button>
      </div>
      {showReader && hasContent
        ? <article style={{ maxWidth: "820px", lineHeight: 1.75 }}>
            <h2>{product.title || product.topic}</h2>
            {product.metadata?.strategy?.subtitle && <p><i>{product.metadata.strategy.subtitle}</i></p>}
            {content.introduction && <><h3>Introdução</h3><p style={{ whiteSpace: "pre-wrap" }}>{content.introduction}</p></>}
            {chapters.map((chapter, index) => <section key={index}><h3>{chapter.title || `Capítulo ${index + 1}`}</h3><p style={{ whiteSpace: "pre-wrap" }}>{chapter.content || ""}</p></section>)}
            {content.conclusion && <><h3>Conclusão</h3><p style={{ whiteSpace: "pre-wrap" }}>{content.conclusion}</p></>}
          </article>
        : !hasContent ? <p>O texto integral ainda não está disponível para leitura.</p> : null}
    </div>
    <div className="panel"><h3>Arquivos do produto</h3>
      {artifacts.map(([kind, url]) => <p key={kind}><b>{kind.toUpperCase()}:</b> <a href={url} target="_blank" rel="noreferrer">abrir ou baixar arquivo ↗</a></p>)}
      {!artifacts.length && <p>Nenhum arquivo final disponível.</p>}
    </div>
  </Page>;
}
function RadarView() {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const evaluate = async () => {
    setBusy(true);
    setNotice("");
    try {
      const data = await call("/api/v1/radar", {
        method: "POST",
        body: JSON.stringify(DEFAULT_RADAR),
      });
      setResult(data);
      setNotice("Avaliação concluída com o motor de pontuação do Hermes.");
    } catch (error) {
      setNotice("Não foi possível avaliar a hipótese: " + error.message);
    } finally {
      setBusy(false);
    }
  };

  return <Page title="Radar de Produtos" sub="Avalia hipóteses de produto digital com critérios internos. Não representa pesquisa de mercado ao vivo nem promessa de vendas.">
    {notice && <div className="notice">{notice}</div>}
    <div className="panel">
      <K>PRODUCT OPPORTUNITY SCORE</K>
      <h3>Critérios de avaliação</h3>
      <p>Demanda hipotética, concorrência, diferenciação, dificuldade de produção, potencial de preço e clareza do público. Ajustes e validação de mercado continuam necessários.</p>
      <Button primary disabled={busy} onClick={evaluate}>{busy ? "Calculando…" : "Avaliar hipótese de produto ↗"}</Button>
    </div>
    {result && <>
      <div className="metric-grid">
        <Metric label="Pontuação" value={result.score} />
        <Metric label="Confiança" value={result.confidence + "%"} />
      </div>
      <div className="panel">
        <h3>Dimensões avaliadas</h3>
        {Object.entries(result.dimensions || {}).map(([name, value]) => <p key={name}><b>{name.replaceAll("_", " ")}:</b> {value}/100</p>)}
        {(result.findings || []).map((finding, index) => <p key={index}>• {finding}</p>)}
      </div>
    </>}
  </Page>;
}
function Publish({ product, integrations }) {
  const [kiwifyProductId, setKiwifyProductId] = useState(product?.metadata?.publications?.kiwify?.product_id || "");
  const [checkoutUrl, setCheckoutUrl] = useState(product?.metadata?.publications?.kiwify?.checkout_url || "");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    setKiwifyProductId(product?.metadata?.publications?.kiwify?.product_id || "");
    setCheckoutUrl(product?.metadata?.publications?.kiwify?.checkout_url || "");
    setNotice("");
  }, [product?.id]);
  if (!product) return <Page title="Publicação" sub="Selecione um produto no catálogo." />;
  const kiwify = product.metadata?.publications?.kiwify;
  const marketingPack = product.metadata?.marketing_pack || {};
  const coverArt = product.metadata?.cover_art || {};
  const qualityGate = product.metadata?.quality_gate || {};
  const commercialReady = product.status === "ready_to_publish"
    && qualityGate.approved === true
    && qualityGate.ai_cover_generated === true
    && coverArt.generated === true
    && ["ai_horde", "ovhcloud"].includes(coverArt.provider)
    && product.metadata?.marketing_pack_status === "ready"
    && typeof marketingPack.product_description === "string"
    && marketingPack.product_description.length >= 300;
  const copyText = async value => {
    try {
      await navigator.clipboard.writeText(String(value || ""));
      setNotice("Texto copiado para a área de transferência.");
    } catch {
      setNotice("Não foi possível copiar automaticamente neste navegador.");
    }
  };
  const saveKiwify = async event => {
    event.preventDefault();
    setSaving(true);
    setNotice("");
    try {
      await call("/api/v1/products/" + product.id + "/publication/kiwify", {
        method: "POST",
        body: JSON.stringify({ product_id: kiwifyProductId.trim() || null, checkout_url: checkoutUrl.trim() })
      });
      setNotice("Link de checkout salvo no Hermes. A compra e a entrega continuam sendo processadas pela Kiwify.");
    } catch (error) { setNotice(error.message); }
    finally { setSaving(false); }
  };
  const rawArtifacts = product.metadata?.artifacts && Object.keys(product.metadata.artifacts).length
    ? product.metadata.artifacts
    : { pdf: product.metadata?.pdf_url, cover: product.metadata?.cover_url, docx: product.metadata?.document_url };
  const artifacts = Object.entries(rawArtifacts).filter(([, value]) => typeof value === "string" && /^https?:\/\//i.test(value));
  return <Page title="Publicação" sub="Vincule o checkout externo ao painel do Hermes.">
    <div className="panel">
      <h3>{product.title || product.topic}</h3>
      <p>Status do produto: <b>{product.status}</b> · arquivos: <b>{artifacts.length ? "disponíveis" : "pendentes"}</b></p>
      <p>Capa IA: <b>{coverArt.generated ? `${coverArt.provider} · ${coverArt.model}` : "pendente"}</b> · texto comercial: <b>{product.metadata?.marketing_pack_status === "ready" ? "pronto" : "pendente"}</b></p>
      <p>O cadastro do produto e o upload do PDF são feitos no painel da Kiwify. O Hermes prepara os materiais, valida o produto e registra o ID e o checkout para acompanhar vendas.</p>
      {!commercialReady && <div className="panel-note">Publicação bloqueada: o ebook precisa de capa IA, revisão aprovada e pacote comercial completo antes de vincular o checkout.</div>}
      <form className="factory-form" onSubmit={saveKiwify}>
        <label>ID do produto Kiwify (opcional)<input value={kiwifyProductId} onChange={e => setKiwifyProductId(e.target.value)} placeholder="ID exibido na URL do produto" /></label>
        <label>Link de checkout HTTPS<input type="url" required value={checkoutUrl} onChange={e => setCheckoutUrl(e.target.value)} placeholder="https://pay.kiwify.com.br/..." /></label>
        <div className="form-footer"><span>Pagamento e entrega continuam na Kiwify.</span><Button primary type="submit" disabled={saving || !checkoutUrl.trim() || !commercialReady}>{saving ? "Salvando…" : "Vincular checkout ↗"}</Button></div>
      </form>
      {notice && <p className="notice">{notice}</p>}
      {kiwify?.checkout_url && <p><b>Checkout registrado:</b> <a href={kiwify.checkout_url} target="_blank" rel="noreferrer">abrir checkout Kiwify ↗</a> · {kiwify.status || "salvo"}</p>}
      <p><a href="https://dashboard.kiwify.com.br/" target="_blank" rel="noreferrer">Abrir painel da Kiwify ↗</a></p>
    </div>
    <div className="panel"><h3>Arquivos para cadastrar na plataforma</h3>
      {artifacts.map(([kind, url]) => <p key={kind}><b>{kind}:</b> <a href={url} target="_blank" rel="noreferrer">abrir arquivo</a></p>)}
      {!artifacts.length && <p>Os links dos arquivos aparecerão após a geração bem-sucedida do produto.</p>}
      <p><a href="https://dashboard.kiwify.com.br/" target="_blank" rel="noreferrer">Abrir painel da Kiwify para cadastrar o produto ↗</a></p>
    </div>
    <div className="panel">
      <div className="section-head"><div><span className="kicker">SALES COPY</span><h3>Descrição e divulgação prontas</h3></div>
        <Button onClick={() => copyText(marketingPack.product_description)} disabled={!marketingPack.product_description}>Copiar descrição</Button>
      </div>
      {marketingPack.product_description
        ? <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{marketingPack.product_description}</p>
        : <p>O pacote comercial será gerado pela Fábrica depois da revisão editorial.</p>}
      {Array.isArray(marketingPack.benefits) && marketingPack.benefits.length > 0 && <><h4>Benefícios descritos no ebook</h4><ul>{marketingPack.benefits.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
      {Array.isArray(marketingPack.faq) && marketingPack.faq.length > 0 && <><h4>Perguntas frequentes</h4>{marketingPack.faq.map((item, index) => <p key={index}><b>{item.question}</b><br />{item.answer}</p>)}</>}
      {Array.isArray(marketingPack.social_posts) && marketingPack.social_posts.length > 0 && <><h4>Posts preparados para divulgação</h4>{marketingPack.social_posts.map((post, index) => <div className="panel-note" key={index}>
        <b>{post.platform}: {post.hook}</b><p>{post.caption}</p><p><b>CTA:</b> {post.cta}</p>
        <Button onClick={() => copyText(`${post.hook}\n\n${post.caption}\n\n${post.cta}`)}>Copiar post</Button>
      </div>)}</>}
    </div>
  </Page>;
}
function SalesView({ data, load }) { return <Page title="Vendas" sub="Dados vindos de eventos reais persistidos."><Button primary onClick={load}>Atualizar vendas</Button>{data ? <div className="metric-grid"><Metric label="Receita" value={data.revenue ?? 0}/><Metric label="Pedidos" value={data.orders ?? 0}/><Metric label="Aprovados" value={data.approved ?? 0}/><Metric label="Reembolsos" value={data.refunds ?? 0}/></div> : <Empty text="Clique em atualizar para consultar as vendas reais." />}</Page>; }
function AnalyticsView({ data, load }) { return <Page title="Analytics" sub="Insights calculados a partir dos dados persistidos."><Button primary onClick={load}>Atualizar analytics</Button>{data ? <div className="two-col"><div className="panel"><pre>{JSON.stringify(data, null, 2)}</pre></div></div> : <Empty text="Nenhuma leitura carregada." />}</Page>; }
function RevenueChannels({ integrations }) {
  const getStatus = name => integrations.find(x => String(x.name || "").toLowerCase() === name.toLowerCase());
  const kiwify = getStatus("Kiwify");
  const supabase = getStatus("Supabase");
  const channels = [
    { name: "Kiwify", type: "Produtos digitais", status: kiwify?.status || "não verificado", detail: kiwify?.message || "O webhook precisa receber uma venda de teste; o cadastro de produto é feito no painel.", action: "Abrir painel Kiwify", url: "https://dashboard.kiwify.com.br/", next: "Criar o produto no painel, enviar PDF, configurar preço e checkout; depois vincular o checkout no Hermes e confirmar o webhook com uma venda de teste." },
    { name: "YouTube", type: "Vídeos e canal dark", status: "roteiros disponíveis", detail: "A Fábrica de Vídeos gera pacotes originais; upload e monetização do canal não estão conectados.", action: "Abrir YouTube Studio", url: "https://studio.youtube.com/", next: "Criar/vincular canal, revisar conteúdo e configurar OAuth oficial antes de automatizar uploads." },
    { name: "TikTok Shop", type: "Afiliados e comércio", status: "cadastro da conta necessário", detail: "O Hermes prepara roteiros para TikTok; não publica vídeos compráveis nem acessa a conta Shop.", action: "Abrir TikTok Shop Brasil", url: "https://seller.tiktok.com/br", next: "Verificar elegibilidade de vendedor/criador, aprovação e permissões no próprio TikTok Shop." },
    { name: "99Freelas", type: "Serviços", status: "revisão manual", detail: "O Radar pode preparar rascunhos; envio automático não está habilitado.", action: "Abrir 99Freelas", url: "https://www.99freelas.com.br/", next: "Revisar o escopo e enviar pela plataforma. Freelancer.com continua pausado." },
    { name: "Workana", type: "Serviços", status: "revisão manual", detail: "Sem integração oficial ativa nesta versão.", action: "Abrir Workana", url: "https://www.workana.com/", next: "Usar somente oportunidades reais, com proposta revisada e sem automatizar candidatura por scraping." },
    { name: "Jobicy", type: "Radar gratuito", status: "API pública", detail: "Fonte pública de vagas remotas; os anúncios podem ser emprego e não necessariamente freela.", action: "Ver documentação", url: "https://jobicy.com/jobs-rss-feed", next: "O Radar captura links de origem; conferir localização, tipo de contrato e elegibilidade." },
    { name: "Himalayas", type: "Radar gratuito", status: "API pública", detail: "Feed público de vagas remotas sem chave de API; manter atribuição e link para o anúncio original.", action: "Ver documentação", url: "https://himalayas.app/docs/remote-jobs-api", next: "Conferir país, contrato, salário e se a vaga aceita candidatos do Brasil." },
  ];
  return <Page title="Canais de Receita" sub="Visão honesta de onde o Hermes pode criar, vender ou encontrar trabalho. Conexão real, cadastro e publicação são estados diferentes.">
    <div className="panel"><K>REGRA OPERACIONAL</K><h3>Nenhuma plataforma será marcada como conectada só porque existe um link ou uma chave.</h3><p>O Hermes deve guardar a evidência da última verificação, mostrar o que falta e pedir aprovação antes de ações financeiras, publicações ou envio de propostas.</p></div>
    <div className="product-grid">{channels.map(channel => <article className="product-card detailed" key={channel.name}><div className="cover-placeholder"><span>{channel.name.slice(0,1)}</span><small>{channel.status}</small></div><div className="product-info"><span className="tag">{channel.type}</span><h4>{channel.name}</h4><p>{channel.detail}</p><div className="panel-note"><b>Próximo passo:</b> {channel.next}</div><div className="asset-actions"><a href={channel.url} target="_blank" rel="noreferrer">{channel.action} ↗</a></div></div></article>)}</div>
    <div className="panel"><h3>Dependência central</h3><p><b>Supabase:</b> {supabase?.status || "não verificado"} — {supabase?.message || "A API não confirmou conexão."}</p><p>Sem persistência funcional, o Hermes não consegue manter fila, memória, produtos e evidências de venda de forma confiável.</p></div>
  </Page>;
}

function ChatView({ chat, input, setInput, send }) {
  return <Page title="Hermes" sub="Chat operacional: comandos explícitos acionam ferramentas reais e retornam evidências.">
    <div className="panel chat-panel">
      <div className="quick-commands">
        <button type="button" onClick={() => setInput("Hermes, verifique o sistema e mostre o status do sistema")}>Verificar sistema</button>
        <button type="button" onClick={() => setInput("Hermes, encontre oportunidades de freelancer e rode o radar")}>Rodar Radar</button>
      </div>
      <div className="chat-history">
        {chat.length ? chat.map((m, i) => <div className={`bubble ${m.role}`} key={i}>
          <span>{m.role === "user" ? "Você" : "Hermes"}</span>
          <p>{m.text}</p>
          {m.meta && <small>{m.meta}</small>}
          {m.action && <div className="action-evidence">
            <strong>Ação executada: {m.action === "radar_cycle" ? "Ciclo do Radar" : m.action === "system_status" ? "Diagnóstico do sistema" : m.action}</strong>
            {m.evidence && <details className="evidence-details">
              <summary>Ver evidências estruturadas</summary>
              <pre>{JSON.stringify(m.evidence, null, 2)}</pre>
            </details>}
          </div>}
        </div>) : <p>Experimente “Verificar sistema” ou “Rodar Radar”. O Hermes deve mostrar o resultado da ferramenta, não apenas afirmar que executou.</p>}
      </div>
      <form className="chat-form" onSubmit={send}>
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Dê uma instrução ao Hermes…" />
        <Button primary type="submit">Enviar ↗</Button>
      </form>
    </div>
  </Page>;
}
function DiagnosticsPanel({ data }) { if (!data) return <Empty text="Diagnóstico ainda não executado." />; return <div className="panel diagnostics-grid">{data.checks.map((x, i) => <div className="diag-row" key={`${x.name}-${i}`}><i className={x.status === "online" || x.status === "ready" ? "online" : "offline"}></i><strong>{x.name}</strong><span>{x.status}</span><small>{x.message || ""}</small></div>)}</div>; }
function Integrations({ items, diagnostics, runDiagnostics }) { return <Page title="Integrações" sub="Estado das conexões sem expor segredos."><Button primary onClick={runDiagnostics}>Testar conexões</Button><DiagnosticsPanel data={diagnostics} /><div className="integration-list">{items.length ? items.map(x => <div className="panel" key={x.name}><strong>{x.name}</strong><p>{x.status}</p><small>{x.message}</small></div>) : <Empty text="Nenhuma integração retornada pelo backend." />}</div></Page>; }
function Experiments({ products, radar }) { return <Page title="Experimentos" sub="Área para comparar temas e resultados reais."><div className="metric-grid"><Metric label="Produtos" value={products.length}/><Metric label="Radar disponível" value={radar ? "sim" : "não"}/></div><Empty text="Os experimentos usam somente produtos e análises persistidos; não há conversões inventadas." /></Page>; }
function Agents() {
  return <Page title="Equipe de agentes" sub="Hermes Chefe coordena Radar, Factory, Dev e Analyst. Tarefas despachadas ficam registradas e podem ser acompanhadas aqui.">
    <AgentControlCenter />
  </Page>;
}
function AgentControlCenter() {
  const [status, setStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [task, setTask] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = async () => {
    try {
      const [nextStatus, nextRuns] = await Promise.all([
        call("/api/v1/agents/status"),
        call("/api/v1/agents/runs")
      ]);
      setStatus(nextStatus);
      setRuns(Array.isArray(nextRuns?.runs) ? nextRuns.runs : []);
    } catch (error) {
      setNotice("Não foi possível atualizar a equipe: " + error.message);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  const dispatch = async event => {
    event.preventDefault();
    const instruction = task.trim();
    if (!instruction) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await call("/api/v1/agents/dispatch", {
        method: "POST",
        body: JSON.stringify({ agent: "Hermes Chefe", input: { prompt: instruction } })
      });
      setNotice("Tarefa enviada para Hermes Chefe. ID: " + result.run_id);
      setTask("");
      await load();
    } catch (error) {
      setNotice("Falha ao despachar tarefa: " + error.message);
    } finally {
      setBusy(false);
    }
  };

  return <>
    {notice && <div className="notice">{notice}</div>}
    {status?.ai_provider_last_error && <div className="panel-note">Última falha do provedor IA: {status.ai_provider_last_error}</div>}
    <div className="metric-grid">
      <Metric label="Chefe" value={status?.chief || "verificando"} />
      <Metric label="Provedor IA" value={status?.ai_provider_status || "verificando"} />
      <Metric label="Worker real" value={status?.worker_status || "verificando"} />
      <Metric label="Fila Redis" value={status?.queue_status || "verificando"} />
      <Metric label="Autonomia de fábrica" value={status?.autonomy_enabled ? "ativa" : "pausada"} />
      <Metric label="Execuções registradas" value={runs.length} />
    </div>
    <div className="panel">
      <h3>Time operacional</h3>
      <p>O Chefe divide cada tarefa entre Radar, Factory, Dev e Analyst, consolida as análises e grava o resultado. A fila é processada pelo worker; esta tela atualiza automaticamente.</p>
      <div className="product-grid">
        {(status?.agents || []).map(agent => <article className="panel" key={agent.name}>
          <strong>{agent.name}</strong>
          <p>{agent.role}</p>
          <span className="tag">{agent.status}</span>
        </article>)}
      </div>
    </div>
    <form className="panel factory-form" onSubmit={dispatch}>
      <label>O que o Hermes Chefe deve executar?
        <textarea value={task} onChange={event => setTask(event.target.value)} minLength={8} required placeholder="Ex.: audite o funil de ebooks, identifique bloqueios de publicação e proponha correções verificáveis." />
      </label>
      <div className="form-footer"><span>Despacho persistente · 4 especialistas + Chefe · histórico salvo</span><Button primary type="submit" disabled={busy || !task.trim()}>{busy ? "Enviando…" : "Despachar para o Chefe ↗"}</Button></div>
    </form>
    <div className="panel">
      <div className="section-heading"><div><h3>Histórico de execuções</h3><p className="panel-note">Atualização automática a cada 10 segundos.</p></div><Button onClick={load}>Atualizar</Button></div>
      {runs.length ? runs.map(run => <article className="job" key={run.id}>
        <div className={`job-icon ${run.status}`}>✦</div>
        <div className="job-main">
          <strong>{run.agent || "Hermes Chefe"}</strong>
          <p>{run.input?.instruction || run.input?.prompt || "Tarefa operacional"}</p>
          {(run.error_message || run.job_error) && <small>{run.error_message || run.job_error}</small>}
          {run.output?.output && <details><summary>Ver resultado consolidado</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{run.output.output}</pre></details>}
        </div>
        <span className={`job-status ${run.job_status || run.status}`}>{run.job_status || run.status}</span>
      </article>) : <Empty text="Nenhuma execução do time registrada ainda. Envie uma tarefa acima para iniciar a primeira." />}
    </div>
    <div className="panel-note">A autonomia de fábrica cria e-books dentro dos limites configurados. Publicação, gastos e envio de propostas continuam sujeitos às permissões e confirmações das plataformas.</div>
  </>;
}
function Automation({ jobs }) { const active = useMemo(() => jobs.filter(j => ["pending", "running", "retrying"].includes(j.status)).length, [jobs]); return <Page title="Automação" sub="Visão operacional da fila e do worker."><div className="metric-grid"><Metric label="Jobs ativos" value={active}/><Metric label="Jobs totais" value={jobs.length}/></div><Empty text="A execução automática ocorre no worker; este painel não finge agendamentos que ainda não existem no backend." /></Page>; }
function Logs({ jobs }) { return <Page title="Logs" sub="Eventos de jobs retornados pelo backend."><div className="job-list">{jobs.map(j => <div className="panel" key={j.id}><strong>{j.status}</strong><p>{j.id}</p><small>{j.error_message || "sem erro"}</small></div>)}</div></Page>; }
function Guides() { return <Page title="Guias" sub="Operação do Hermes Pro."><div className="two-col"><div className="panel"><h3>1. Conexão</h3><p>Vercel hospeda a interface. O backend fica no Render. O cliente usa o proxy Vercel e cai para o Render diretamente quando o proxy falhar.</p></div><div className="panel"><h3>2. Produção</h3><p>Fábrica cria produto e job. Redis entrega ao worker. Gemini produz e revisa conteúdo. Supabase persiste estado e artefatos.</p></div><div className="panel"><h3>3. Hotmart</h3><p>O Hermes consulta o catálogo disponível e recebe vendas por webhook. A criação inicial do produto continua no painel Hotmart.</p></div><div className="panel"><h3>4. Se estiver offline</h3><p>Abra Integrações e execute o diagnóstico. Se Render estiver offline, o painel mostrará a conexão necessária em vez de um erro NOT_FOUND genérico.</p></div></div></Page>; }

createRoot(document.getElementById("root")).render(<App />);
