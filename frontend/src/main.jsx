import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { call, diagnose } from "./api.js";
import "./style.css";
import "./diagnostics.css";

const NAV = [
  ["⌂", "Início"], ["✦", "Hermes"], ["⌁", "Radar"], ["⚗", "Fábrica"], ["◈", "Produtos"],
  ["▣", "Studio"], ["↗", "Publicação"], ["$", "Vendas"], ["◌", "Analytics"], ["◇", "Experimentos"],
  ["▶", "Vídeos"], ["◉", "Canais"], ["◎", "Agentes"], ["⟳", "Automação"], ["⌘", "Integrações"], ["≡", "Logs"], ["?", "Guias"], ["▤", "Jobs"]
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
  const [videoChannel, setVideoChannel] = useState("youtube_shorts");
  const [videoTopic, setVideoTopic] = useState("");
  const [videoPackage, setVideoPackage] = useState(null);
  const refreshing = useRef(false);

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
    catch (error) { if (path === "/health") setNotice(error.message); return null; }
  };

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30000);
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

  const generateVideoPackage = async (event) => {
    event.preventDefault();
    const topic = videoTopic.trim();
    if (topic.length < 5) { setNotice("Informe um tema com pelo menos 5 caracteres."); return; }
    const result = await action(() => call("/api/v1/content/video-package", {
      method: "POST",
      body: JSON.stringify({ topic, channel: videoChannel })
    }), "Pacote de vídeo gerado para revisão; nada foi publicado.");
    if (result) setVideoPackage(result);
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
      {view === "Vídeos" && <VideoFactory channel={videoChannel} setChannel={setVideoChannel} topic={videoTopic} setTopic={setVideoTopic} result={videoPackage} submit={generateVideoPackage} busy={busy} />}
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
function RadarView() {
  const [items,setItems]=useState([]); const [busy,setBusy]=useState(false); const [notice,setNotice]=useState(""); const [drafts,setDrafts]=useState({});
  const load=async()=>{try{const data=await call("/api/v1/opportunities?limit=20");setItems(Array.isArray(data)?data:[]);return Array.isArray(data)?data:null;}catch(e){setNotice(e.message);return null;}};
  useEffect(()=>{load();},[]);
  const run=async()=>{setBusy(true);setNotice("");try{const scan=await call("/api/v1/autonomy/cycle",{method:"POST",body:JSON.stringify({})});await load();setNotice("Varredura real concluída: "+Number(scan.scanned||0)+" oportunidades encontradas; "+Number(scan.queued||0)+" tarefas preparadas. Nenhuma proposta foi enviada.");}catch(e){setNotice("A varredura não foi concluída: "+e.message);}finally{setBusy(false);}};
  const queue=async(id)=>{try{const r=await call("/api/v1/opportunities/"+id+"/queue",{method:"POST"});setDrafts(old=>({...old,[id]:r.proposal||""}));setNotice(r.message||"Rascunho preparado para revisão.");await load();}catch(e){setNotice(e.message);}};
  return <Page title="Radar" sub="Busca oportunidades reais em APIs públicas gratuitas, salva os resultados e prepara rascunhos para revisão. O envio continua manual.">
    {notice&&<div className="notice">{notice}</div>}
    <Button primary disabled={busy} onClick={run}>{busy?"Atualizando…":"↻ Varrer a internet agora"}</Button>
    <div className="section-heading"><div><K>OPPORTUNITIES</K><h3>Fila priorizada</h3></div><span className="kicker">{items.length} carregadas</span></div>
    <div className="product-grid">{items.length?items.map(x=><article className="product-card detailed" key={x.id}>
      <div className="cover-placeholder"><span>{String(x.source||"R").slice(0,1).toUpperCase()}</span><small>{"score "+Math.round(Number(x.score||0))}</small></div>
      <div className="product-info"><span className="tag">{x.source||"RADAR"}</span><h4>{x.title}</h4><p>{x.summary||x.description||"Descrição detalhada não capturada; confira o anúncio original."}</p><div className="product-meta"><span>{x.difficulty||"—"}</span><span>{x.suggested_price?(x.currency||"BRL")+" "+x.suggested_price:"preço pendente"}</span></div><div className="asset-actions"><a href={x.url||x.source_url} target="_blank" rel="noreferrer">Abrir oportunidade</a><button onClick={()=>queue(x.id)}>Gerar rascunho</button></div>{drafts[x.id]&&<div className="panel"><h4>Proposta — revisar antes de enviar</h4><pre style={{whiteSpace:"pre-wrap"}}>{drafts[x.id]}</pre><button onClick={()=>navigator.clipboard.writeText(drafts[x.id]).then(()=>setNotice('Proposta copiada.')).catch(()=>setNotice('Não foi possível copiar automaticamente; selecione o texto da proposta.'))}>Copiar proposta</button></div>}</div>
    </article>):<Empty text="Nenhuma oportunidade freelance relevante salva ainda."/>}</div>
  </Page>;
}
function Publish({ product, integrations }) { const hotmart = integrations.find(x => x.name?.toLowerCase().includes("hotmart")); return <Page title="Publicação" sub="Preparação comercial e sincronização do catálogo Hotmart."><div className="panel"><h3>{product?.title || product?.topic || "Nenhum produto selecionado"}</h3><p>Hotmart: <b>{hotmart?.status || "não verificada"}</b></p><p>Artefatos: <b>{Object.keys(product?.metadata?.artifacts || {}).length ? "gerados" : "pendentes"}</b></p><p>A API pública da Hotmart permite consultar/sincronizar produtos e ofertas e receber webhooks. A criação de um novo produto digital continua no painel da Hotmart; o Hermes não simula uma publicação que a API não documenta.</p></div></Page>; }
function SalesView({ data, load }) { return <Page title="Vendas" sub="Dados vindos de eventos reais persistidos."><Button primary onClick={load}>Atualizar vendas</Button>{data ? <div className="metric-grid"><Metric label="Receita" value={data.revenue ?? 0}/><Metric label="Pedidos" value={data.orders ?? 0}/><Metric label="Aprovados" value={data.approved ?? 0}/><Metric label="Reembolsos" value={data.refunds ?? 0}/></div> : <Empty text="Clique em atualizar para consultar as vendas reais." />}</Page>; }
function AnalyticsView({ data, load }) { return <Page title="Analytics" sub="Insights calculados a partir dos dados persistidos."><Button primary onClick={load}>Atualizar analytics</Button>{data ? <div className="two-col"><div className="panel"><pre>{JSON.stringify(data, null, 2)}</pre></div></div> : <Empty text="Nenhuma leitura carregada." />}</Page>; }
function RevenueChannels({ integrations }) {
  const getStatus = name => integrations.find(x => String(x.name || "").toLowerCase() === name.toLowerCase());
  const hotmart = getStatus("Hotmart");
  const supabase = getStatus("Supabase");
  const channels = [
    { name: "Hotmart", type: "Produtos digitais", status: hotmart?.status || "não verificado", detail: hotmart?.message || "A API ainda não confirmou a conexão.", action: "Abrir painel Hotmart", url: "https://app.hotmart.com/", next: "Conectar credenciais oficiais e configurar webhook; publicar o produto no painel até existir fluxo de criação aprovado." },
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

function VideoFactory({ channel, setChannel, topic, setTopic, result, submit, busy }) {
  return <Page title="Fábrica de Vídeos" sub="Crie roteiros originais para YouTube e canais verticais. Gera o pacote de produção; renderização e publicação são etapas separadas.">
    <div className="two-col">
      <form className="panel factory-form" onSubmit={submit}>
        <label>Canal de destino
          <select value={channel} onChange={e => setChannel(e.target.value)}>
            <option value="youtube_shorts">YouTube Shorts</option>
            <option value="youtube_long">YouTube — vídeo longo</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram_reels">Instagram Reels</option>
          </select>
        </label>
        <label>Tema / nicho do vídeo
          <textarea value={topic} onChange={e => setTopic(e.target.value)} minLength={5} required placeholder="Ex.: curiosidades históricas brasileiras com fontes verificáveis" />
        </label>
        <div className="form-footer"><span>Roteiro · narração · cenas · legenda · hashtags</span><Button primary type="submit" disabled={busy}>Gerar pacote ↗</Button></div>
        <p className="panel-note">Usa o modelo de IA já configurado. Pode consumir a franquia/cota da chave existente; não compra ferramentas nem publica automaticamente.</p>
      </form>
      <div className="panel">
        <K>FLUXO DE PRODUÇÃO</K><h3>Da ideia ao canal</h3>
        <div className="pipeline"><span>IDEIA</span><span>→ ROTEIRO</span><span>→ CENAS</span><span>→ REVISÃO</span><span>→ RENDER</span><span>→ PUBLICAÇÃO</span></div>
        <p>O pacote inclui títulos, gancho, roteiro com timestamps, narração, prompts visuais, texto na tela, legenda, hashtags, CTA e pontos factuais que precisam de checagem.</p>
        <p><b>Monetização:</b> respeitar as regras de conteúdo original, direitos autorais e elegibilidade de cada plataforma. Um roteiro gerado não é uma venda nem um vídeo publicado.</p>
      </div>
    </div>
    {result && <div className="panel"><div className="section-heading"><div><K>PACOTE GERADO</K><h3>{result.topic}</h3></div><span className="tag">{result.provider} · {result.model}</span></div><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",fontFamily:"inherit",lineHeight:1.65}}>{result.package}</pre><p className="panel-note">{result.message}</p></div>}
  </Page>;
}

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
