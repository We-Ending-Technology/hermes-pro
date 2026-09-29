import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { formatCurrency, navItems, statusTone } from "./lib/ui.js";
import { getProductAssets, getEditableContent } from "./lib/productWorkspace.js";
import "./style.css";
import "./workspace.css";

const API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-commercial.onrender.com";

const agentCatalog = [
  ["RADAR", "Descobre sinais e oportunidades", "radar"],
  ["STRATEGIST", "Valida potencial e margem", "strategy"],
  ["WRITER", "Produz conteúdo", "writer"],
  ["EDITOR", "Revisa e prepara QA", "reviewer"],
  ["DESIGNER", "Prepara identidade e ativos", "designer"],
  ["PUBLISHER", "Prepara canais de venda", "publisher"],
  ["GUARDIAN", "Protege orçamento e qualidade", "supervisor"],
];

async function jsonFetch(path, options = {}) {
  const response = await fetch(`${API}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
  return body;
}

function App() {
  const [view, setView] = useState("Início");
  const [data, setData] = useState({ dashboard: null, products: [], jobs: [], opportunities: [], integrations: [], sales: null, analytics: null });
  const [online, setOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [topic, setTopic] = useState("");
  const [chat, setChat] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [selected, setSelected] = useState(null);
  const [mobileNav, setMobileNav] = useState(false);

  async function refresh() {
    try {
      const [health, dashboard, products, jobs, opportunities, integrations, sales, analytics] = await Promise.all([
        jsonFetch("/health"),
        jsonFetch("/api/v1/dashboard"),
        jsonFetch("/api/v1/products"),
        jsonFetch("/api/v1/jobs"),
        jsonFetch("/api/v1/opportunities").catch(() => []),
        jsonFetch("/api/v1/integrations").catch(() => []),
        jsonFetch("/api/v1/sales").catch(() => null),
        jsonFetch("/api/v1/analytics").catch(() => null),
      ]);
      setOnline(health?.status === "ok");
      setData({ dashboard, products, jobs, opportunities, integrations, sales, analytics });
      if (selected?.id) {
        const fresh = products.find(product => product.id === selected.id);
        if (fresh) setSelected(fresh);
      }
    } catch (error) {
      setOnline(false);
      setNotice(error.message);
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, []);

  async function createProduct(event) {
    event.preventDefault();
    const value = topic.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      const product = await jsonFetch("/api/v1/products", { method: "POST", body: JSON.stringify({ topic: value }) });
      setTopic("");
      setSelected(product);
      setView("Produtos");
      setNotice("Produção iniciada. O worker assumiu o job.");
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendChat(event) {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text || busy) return;
    setChat(items => [...items, { role: "user", text }]);
    setChatInput("");
    setBusy(true);
    try {
      const response = await jsonFetch("/api/v1/chat", { method: "POST", body: JSON.stringify({ message: text }) });
      setChat(items => [...items, { role: "assistant", text: response.response, meta: `${response.provider} · ${response.model}` }]);
      await refresh();
    } catch (error) {
      setChat(items => [...items, { role: "assistant", text: `Erro do Hermes: ${error.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  const activeJobs = data.jobs.filter(job => ["pending", "running", "retrying"].includes(job.status)).length;
  const readyProducts = data.products.filter(product => ["ready_to_sell", "completed"].includes(product.status)).length;
  const revenue = data.sales?.revenue ?? data.dashboard?.revenue;

  return (
    <div className="app-shell">
      <div className={`mobile-overlay ${mobileNav ? "show" : ""}`} onClick={() => setMobileNav(false)} />
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand-row"><div className="brand-orb">H</div><div><strong>HERMES</strong><span>AUTONOMOUS COMMERCE</span></div></div>
        <div className={`system-state ${online ? "live" : "down"}`}><i /> <span>{online ? "Sistema operacional" : "Conexão pendente"}</span><small>{online ? "LIVE" : "OFFLINE"}</small></div>
        <nav className="main-nav">{navItems.map((item, index) => <button key={item} className={view === item ? "active" : ""} onClick={() => { setView(item); setMobileNav(false); }}><NavIcon index={index} /><span>{item}</span></button>)}</nav>
        <div className="sidebar-bottom"><div className="mini-budget"><span>Meta operacional</span><strong>R$ 900/dia</strong><div><i style={{ width: `${Math.min(100, Number(revenue || 0) / 9)}%` }} /></div><small>{revenue != null ? `${formatCurrency(revenue)} acumulado` : "Sem vendas registradas"}</small></div><button className="refresh-btn" onClick={refresh}>↻ Sincronizar agora</button></div>
      </aside>
      <main className="main-content">
        <header className="topbar"><button className="mobile-menu" onClick={() => setMobileNav(true)}>☰</button><div className="crumbs"><span>HERMES</span><b>/</b><strong>{view}</strong></div><div className="top-actions"><div className="system-time"><span className="pulse-dot" /> 24/7 AUTONOMOUS</div><button className="round-btn" onClick={refresh}>↻</button><div className="profile">W</div></div></header>
        {notice && <div className="notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
        {view === "Início" && <Home data={data} online={online} activeJobs={activeJobs} readyProducts={readyProducts} revenue={revenue} go={setView} />}
        {view === "Radar" && <Radar opportunities={data.opportunities} />}
        {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} submit={createProduct} busy={busy} />}
        {view === "Produtos" && <Products items={data.products} selected={selected} setSelected={setSelected} />}
        {view === "Vendas" && <Sales sales={data.sales} revenue={revenue} />}
        {view === "Analytics" && <Analytics analytics={data.analytics} data={data} />}
        {view === "Agentes" && <Agents online={online} />}
        <button className="hermes-float" onClick={() => setView("Hermes")}><span>H</span><div><b>Hermes</b><small>Fale comigo</small></div><i>↗</i></button>
        {view === "Hermes" && <Chat chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} busy={busy} />}
      </main>
    </div>
  );
}

function NavIcon({ index }) { const glyphs = ["⌂", "⌁", "✦", "▣", "◈", "◒", "◎"]; return <b className="nav-icon">{glyphs[index]}</b>; }

function Home({ data, online, activeJobs, readyProducts, revenue, go }) { const products = data.products || []; return <section className="page"><div className="command-hero"><div className="hero-copy"><div className="eyebrow"><i /> COMMAND CENTER · {online ? "LIVE" : "CONNECTING"}</div><h1>O comércio roda.<br /><em>Você decide.</em></h1><p>Hermes encontra oportunidades, coordena agentes, produz ativos e mede o resultado em um único centro de comando.</p><div className="hero-actions"><button className="primary" onClick={() => go("Fábrica")}>✦ Criar produto</button><button className="ghost" onClick={() => go("Radar")}>Ver Radar →</button></div></div><div className="hero-visual"><div className="ring ring-a" /><div className="ring ring-b" /><div className="core">H<span>AI</span></div><div className="orbit-label l1">RADAR</div><div className="orbit-label l2">QA</div><div className="orbit-label l3">SALES</div></div><div className="hero-caption"><span>ENGINE STATUS</span><strong><i className="live-dot" /> Descobrindo oportunidades</strong><small>Próxima varredura automática · contínua</small></div></div><div className="stats-grid"><Stat label="Receita" value={formatCurrency(revenue)} hint="resultado registrado" accent="violet" /><Stat label="Produtos" value={products.length} hint={`${readyProducts} prontos`} accent="cyan" /><Stat label="Jobs ativos" value={activeJobs} hint="worker em execução" accent="green" /><Stat label="Oportunidades" value={data.opportunities.length} hint="sinais no radar" accent="amber" /></div><div className="section-head"><div><span className="eyebrow">OPERATIONS</span><h2>Visão operacional</h2></div><button onClick={() => go("Agentes")} className="text-link">Ver agentes →</button></div><div className="ops-grid"><div className="panel pipeline-panel"><PanelHead title="Pipeline autônomo" meta="EM TEMPO REAL" /><div className="pipeline-modern">{[["01","RADAR","Sinais"],["02","DECISÃO","Score"],["03","PRODUÇÃO","Ativos"],["04","QA","Validação"],["05","RESULTADO","Métricas"]].map((step,i)=><div className={`pipeline-step ${i===2?"current":i<2?"done":""}`} key={step[0]}><b>{step[0]}</b><strong>{step[1]}</strong><span>{step[2]}</span>{i<4&&<i>→</i>}</div>)}</div><p className="panel-foot">Cada etapa registra estado, tentativa e resultado. Falhas ficam bloqueadas antes da publicação.</p></div><div className="panel health-panel"><PanelHead title="Saúde do sistema" meta={online?"NORMAL":"ATENÇÃO"}/><HealthRow name="API" value={online?"Online":"Offline"} tone={online?"success":"danger"}/><HealthRow name="Persistência" value="Supabase" tone="neutral"/><HealthRow name="IA" value="Gateway" tone="neutral"/><HealthRow name="Worker" value={activeJobs?"Processando":"Aguardando"} tone={activeJobs?"active":"neutral"}/><HealthRow name="Radar" value="24/7" tone="active"/></div></div><div className="section-head"><div><span className="eyebrow">RECENT WORK</span><h2>Produção recente</h2></div><button onClick={()=>go("Produtos")} className="text-link">Abrir catálogo →</button></div>{products.length?<div className="product-strip">{products.slice(0,3).map(p=><ProductMini key={p.id} product={p}/>)}</div>:<EmptyState title="Nenhum produto produzido ainda" text="Dê um comando ao Hermes ou abra a Fábrica para iniciar o primeiro ciclo." action="Abrir Fábrica" onClick={()=>go("Fábrica")}/>}</section>; }

function Stat({ label,value,hint,accent }) { return <article className={`stat-card ${accent}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small><i/></article>; }
function PanelHead({ title,meta }) { return <div className="panel-head"><h3>{title}</h3><span>{meta}</span></div>; }
function HealthRow({ name,value,tone }) { return <div className="health-row"><span>{name}</span><strong><i className={`status-dot ${tone}`}/>{value}</strong></div>; }
function EmptyState({ title,text,action,onClick }) { return <div className="empty-state"><div className="empty-icon">✦</div><h3>{title}</h3><p>{text}</p>{action&&<button className="primary" onClick={onClick}>{action}</button>}</div>; }
function ProductMini({ product }) { const assets=getProductAssets(product); return <article className="product-mini"><div className="cover-mini">{assets.cover?<img src={assets.cover} alt="Capa"/>:<b>H</b>}</div><div><span>{product.status}</span><h3>{product.title||product.metadata?.title||product.topic}</h3><small>{product.current_stage||"pipeline"}</small></div><b className={`status-chip ${statusTone(product.status)}`}>{product.status}</b></article>; }

function Radar({ opportunities }) { return <section className="page"><PageTitle eyebrow="OPPORTUNITY RADAR" title="Onde Hermes deve agir?" text="Sinais públicos são coletados continuamente. Nenhum sinal é tratado como prova de demanda sem validação."/><div className="radar-top"><div className="radar-score"><span>RADAR SCORE</span><strong>{opportunities.length?Math.round(Math.max(...opportunities.map(x=>Number(x.score||0)))):"—"}</strong><small>confiança depende dos dados disponíveis</small></div><div className="radar-ring"><div><b>{opportunities.length}</b><span>sinais</span></div></div></div><div className="opportunity-list">{opportunities.length?opportunities.slice(0,12).map(item=><article className="opportunity" key={item.id}><div className="opp-icon">⌁</div><div><span>{item.source||"signal"}</span><h3>{item.title}</h3><p>{item.description}</p></div><div className="opp-score"><strong>{Math.round(Number(item.score||0))}</strong><small>{Math.round(Number(item.confidence||0)*100)}% conf.</small></div></article>):<EmptyState title="Radar ainda sem sinais persistidos" text="O ciclo autônomo fará novas descobertas quando a persistência estiver disponível."/>}</div></section>; }

function Factory({ topic,setTopic,submit,busy }) { return <section className="page factory-page"><PageTitle eyebrow="PRODUCT FACTORY" title="Construa algo que merece ser vendido." text="Informe uma oportunidade. O Hermes cria o job e acompanha produção, revisão, documentos e ativos."/><div className="factory-layout"><form className="factory-card" onSubmit={submit}><div className="input-label"><span>BRIEFING</span><small>mínimo 3 caracteres</small></div><textarea value={topic} onChange={e=>setTopic(e.target.value)} placeholder="Ex.: Guia prático de IA para pequenos negócios brasileiros" required minLength={3}/><div className="suggestions"><button type="button" onClick={()=>setTopic("Guia prático de IA para pequenos negócios")}>IA para negócios</button><button type="button" onClick={()=>setTopic("Organização financeira para autônomos")}>Finanças</button><button type="button" onClick={()=>setTopic("Currículo e LinkedIn para primeira vaga")}>Carreira</button></div><button className="primary wide" disabled={busy}>{busy?"Iniciando…":"✦ Iniciar produção"}</button></form><div className="factory-side"><div className="factory-stat"><span>01</span><b>Estratégia</b><small>tema → oferta</small></div><div className="factory-stat"><span>02</span><b>Produção</b><small>conteúdo + documentos</small></div><div className="factory-stat"><span>03</span><b>Qualidade</b><small>QA antes de publicar</small></div><div className="factory-stat"><span>04</span><b>Resultado</b><small>medição e otimização</small></div></div></div></section>; }

function Products({ items,selected,setSelected }) { return <section className="page"><PageTitle eyebrow="PRODUCTS" title="Portfólio vivo" text="Cada produto mantém seus ativos, estágio, qualidade e prontidão comercial no mesmo workspace."/><div className="catalog-toolbar"><span>{items.length} produtos</span><div><button>Todos</button><button>Em produção</button><button>Prontos</button></div></div>{items.length?<div className="catalog-grid">{items.map(product=><ProductCard key={product.id} product={product} selected={selected?.id===product.id} onClick={()=>setSelected(product)}/>)}</div>:<EmptyState title="Seu catálogo está vazio" text="Comece pela Fábrica. O produto aparecerá aqui assim que o job for criado."/>}{selected&&<ProductWorkspace product={selected} close={()=>setSelected(null)}/>}</section>; }
function ProductCard({ product,selected,onClick }) { const assets=getProductAssets(product); const m=product.metadata||{}; const title=product.title||m.title||product.topic; return <article className={`catalog-card ${selected?"selected":""}`} onClick={onClick}><div className="catalog-cover">{assets.cover?<img src={assets.cover} alt="Capa"/>:<><b>H</b><span>{product.current_stage||"FACTORY"}</span></>}</div><div className="catalog-body"><div><span className={`status-chip ${statusTone(product.status)}`}>{product.status}</span><small>{product.current_stage||"—"}</small></div><h3>{title}</h3><p>{m.subtitle||product.topic}</p><div className="catalog-foot"><span>QA {m.quality_score??"—"}/100</span><b>{m.suggested_price!=null?formatCurrency(m.suggested_price):"Preço pendente"}</b></div></div></article>; }

function ProductWorkspace({ product,close }) {
  const [studio,setStudio]=useState(null);
  const [content,setContent]=useState(getEditableContent(product));
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const assets=useMemo(()=>getProductAssets(studio?.product||product),[studio,product]);
  const title=(studio?.title||product.title||product.topic);

  async function load(){
    try { const result=await jsonFetch(`/api/v1/studio/${product.id}`); setStudio(result); setContent(result.content||getEditableContent(product)); }
    catch(error){ setMessage(error.message); }
  }
  useEffect(()=>{ load(); },[product.id]);

  function updateChapter(index,key,value){ setContent(current=>({...current,chapters:current.chapters.map((chapter,i)=>i===index?{...chapter,[key]:value}:chapter)})); }
  function addChapter(){ setContent(current=>({...current,chapters:[...(current.chapters||[]),{title:`Capítulo ${(current.chapters?.length||0)+1}`,content:""}]})); }
  function removeChapter(index){ setContent(current=>({...current,chapters:current.chapters.filter((_,i)=>i!==index)})); }

  async function save(){ setBusy(true); setMessage(""); try { await jsonFetch(`/api/v1/studio/${product.id}`,{method:"PUT",body:JSON.stringify({content,note:"Edição manual no Studio"})}); setMessage("Edição salva."); await load(); } catch(error){ setMessage(error.message); } finally { setBusy(false); } }
  async function regenerate(){ setBusy(true); setMessage(""); try { const result=await jsonFetch(`/api/v1/studio/${product.id}/regenerate`,{method:"POST"}); setStudio(result); setMessage("PDF e DOCX regenerados."); await load(); } catch(error){ setMessage(error.message); } finally { setBusy(false); } }
  async function generateCover(){ setBusy(true); setMessage(""); try { const result=await jsonFetch(`/api/v1/studio/${product.id}/cover`,{method:"POST",body:JSON.stringify({prompt:"capa editorial premium",subtitle:studio?.product?.metadata?.subtitle||product.metadata?.subtitle||""})}); setStudio(current=>({...current,product:result.product})); setMessage("Capa gerada."); await load(); } catch(error){ setMessage(error.message); } finally { setBusy(false); } }

  return <div className="drawer-backdrop" onClick={close}><aside className="drawer" style={{maxWidth:"1100px",width:"min(1100px,96vw)"}} onClick={e=>e.stopPropagation()}><button className="drawer-close" onClick={close}>×</button><div className="product-workspace"><button className="back-button" onClick={close}>← Voltar aos produtos</button><div className="workspace-head"><div><span className="eyebrow">PRODUCT STUDIO</span><h2>{title}</h2><p className="workspace-subtitle">Leia, edite, regenere documentos e controle a capa no mesmo lugar.</p></div><div className="status-stack"><strong>{studio?.product?.status||product.status}</strong><span>{studio?.product?.current_stage||product.current_stage}</span>{message&&<small>{message}</small>}</div></div><div className="workspace-grid"><div><div className="asset-panel"><div className="panel-title"><span>CAPA</span></div>{assets.cover?<img className="full-cover" src={assets.cover} alt={`Capa de ${title}`}/>:<div className="asset-empty"><strong>Capa ainda não disponível</strong><span>Gere a capa aqui quando o conteúdo estiver salvo.</span></div>}<div className="reader-actions"><button className="secondary" onClick={generateCover} disabled={busy}>Gerar nova capa</button></div></div><div className="asset-panel"><div className="panel-title"><span>LEITOR PDF</span></div>{assets.pdf?<><iframe className="pdf-reader" src={assets.pdf} title={`Leitor de ${title}`}/><div className="reader-actions"><a className="link-button secondary" href={assets.pdf} target="_blank" rel="noreferrer">Abrir PDF</a><a className="link-button secondary" href={assets.docx} target="_blank" rel="noreferrer">Abrir DOCX</a></div></>:<div className="asset-empty"><strong>PDF ainda não gerado</strong><span>Quando o job terminar, o leitor aparecerá aqui.</span></div>}</div></div><div><div className="details-panel content-panel"><h3>Editor do e-book</h3><label className="input-label"><span>INTRODUÇÃO</span><textarea value={content.introduction||""} onChange={e=>setContent({...content,introduction:e.target.value})}/></label>{(content.chapters||[]).map((chapter,index)=><div className="content-section" key={index}><div style={{display:"flex",justifyContent:"space-between",gap:8}}><h4>Capítulo {index+1}</h4><button className="secondary" onClick={()=>removeChapter(index)}>Excluir</button></div><input className="workspace-editor-input" value={chapter.title||""} onChange={e=>updateChapter(index,"title",e.target.value)} /><textarea className="workspace-editor-textarea" value={chapter.content||""} onChange={e=>updateChapter(index,"content",e.target.value)}/></div>)}<button className="secondary" onClick={addChapter}>+ Adicionar capítulo</button><label className="input-label" style={{marginTop:15}}><span>CONCLUSÃO</span><textarea value={content.conclusion||""} onChange={e=>setContent({...content,conclusion:e.target.value})}/></label><div className="reader-actions"><button className="primary" onClick={save} disabled={busy}>{busy?"Salvando…":"Salvar edição"}</button><button className="secondary" onClick={regenerate} disabled={busy}>Regenerar PDF/DOCX</button></div></div><div className="details-panel"><h3>Arquivos e estado</h3><div className="file-row"><span>PDF</span><strong>{assets.pdf?"Disponível":"Pendente"}</strong>{assets.pdf&&<a href={assets.pdf} target="_blank" rel="noreferrer">Abrir</a>}</div><div className="file-row"><span>DOCX</span><strong>{assets.docx?"Disponível":"Pendente"}</strong>{assets.docx&&<a href={assets.docx} target="_blank" rel="noreferrer">Abrir</a>}</div><div className="file-row"><span>Capa</span><strong>{assets.cover?"Disponível":"Pendente"}</strong>{assets.cover&&<a href={assets.cover} target="_blank" rel="noreferrer">Abrir</a>}</div></div></div></div></div></aside></div>;
}

function Sales({ sales,revenue }) { return <section className="page"><PageTitle eyebrow="SALES COMMAND" title="Resultado, não vaidade." text="Receita e pedidos registrados pelas integrações. Dados ausentes permanecem ausentes."/><div className="sales-hero"><div><span>RECEITA REGISTRADA</span><strong>{formatCurrency(revenue)}</strong><small>{sales?.orders??0} pedidos registrados</small></div><div className="chart-bars">{[32,45,28,64,51,72,58,82,67,91,76,100].map((height,i)=><i key={i} style={{height:`${height}%`}}/>)}</div></div><div className="stats-grid compact"><Stat label="Pedidos" value={sales?.orders??0} hint="registrados" accent="cyan"/><Stat label="Ticket" value={sales?.average_order_value!=null?formatCurrency(sales.average_order_value):"R$ —"} hint="médio" accent="violet"/><Stat label="Reembolsos" value={sales?.refunds??"—"} hint="sem dado" accent="amber"/></div></section>; }
function Analytics({ analytics,data }) { return <section className="page"><PageTitle eyebrow="ANALYTICS" title="O que o sistema está aprendendo?" text="Analytics transforma eventos e resultados em próximos movimentos. Sem inventar métricas."/><div className="analytics-grid"><div className="panel large-analytics"><PanelHead title="Performance" meta="LIVE DATA"/><div className="big-number">{analytics?.summary??"Dados insuficientes"}</div><div className="signal-bars"><i style={{height:"36%"}}/><i style={{height:"58%"}}/><i style={{height:"44%"}}/><i style={{height:"71%"}}/><i style={{height:"64%"}}/><i style={{height:"84%"}}/><i style={{height:"78%"}}/></div></div><div className="panel"><PanelHead title="Sinais" meta="AGORA"/><HealthRow name="Oportunidades" value={String(data.opportunities.length)} tone="active"/><HealthRow name="Produtos" value={String(data.products.length)} tone="success"/><HealthRow name="Jobs" value={String(data.jobs.length)} tone="neutral"/><HealthRow name="Integrações" value={String(data.integrations.length)} tone="neutral"/></div></div></section>; }
function Agents({ online }) { return <section className="page"><PageTitle eyebrow="AGENT ORCHESTRATOR" title="Uma equipe digital em operação." text="Agentes especializados recebem tarefas do núcleo do Hermes. O status visual distingue operação real de disponibilidade."/><div className="agent-grid-premium">{agentCatalog.map(([name,desc,agent])=><article className="agent-card" key={name}><div className="agent-icon">✦</div><div><span>{agent.toUpperCase()}</span><h3>{name}</h3><p>{desc}</p></div><b className={`agent-state ${online?"ready":"waiting"}`}>{online?"READY":"WAIT"}</b></article>)}</div></section>; }
function Chat({ chat,input,setInput,send,busy }) { return <section className="chat-page"><div className="chat-head"><div className="hermes-avatar">H</div><div><span className="eyebrow">HERMES CORE</span><h2>Command chat</h2><p>Converse, analise ou peça uma ação. O Hermes só declara como concluído o que realmente executou.</p></div></div><div className="chat-window">{chat.length===0&&<div className="chat-welcome"><div className="core-large">H</div><h3>Qual é a próxima decisão?</h3><p>Ex.: “Encontre oportunidades para hoje” ou “Crie um produto sobre IA para pequenos negócios”.</p><div className="prompt-grid"><button onClick={()=>setInput("Encontre oportunidades para hoje")}>Radar de hoje</button><button onClick={()=>setInput("Crie um produto sobre IA para pequenos negócios")}>Criar produto</button><button onClick={()=>setInput("Explique o estado atual do sistema")}>Diagnóstico</button></div></div>}{chat.map((message,index)=><div className={`chat-message ${message.role}`} key={index}><span>{message.role==="user"?"VOCÊ":"HERMES"}</span><p>{message.text}</p>{message.meta&&<small>{message.meta}</small>}</div>)}<form className="chat-form" onSubmit={send}><input value={input} onChange={e=>setInput(e.target.value)} placeholder="Dê um comando ao Hermes…" maxLength={4000}/><button className="primary" disabled={busy}>{busy?"…":"Enviar ↗"}</button></form></div></section>; }
function PageTitle({ eyebrow,title,text }) { return <div className="page-title"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div>; }

createRoot(document.getElementById("root")).render(<App />);
