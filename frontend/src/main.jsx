import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-feature.onrender.com";
const nav = [
  ["⌂", "Início"], ["✦", "Hermes"], ["◈", "Produtos"], ["⚗", "Fábrica"],
  ["⌁", "Radar"], ["↗", "Vendas"], ["◌", "Analytics"], ["◎", "Agentes"], ["?", "Guias"],
];

function App() {
  const [view, setView] = useState("Início");
  const [topic, setTopic] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState([]);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [apiOnline, setApiOnline] = useState(false);
  const [data, setData] = useState({ jobs: 0, products: 0, running: 0, failures: 0, worker: "unavailable" });
  const [products, setProducts] = useState([]);
  const [jobs, setJobs] = useState([]);

  async function refresh() {
    setLoading(true);
    try {
      const [health, dashboard, productList, jobList] = await Promise.all([
        fetch(`${API}/health`), fetch(`${API}/api/v1/dashboard`), fetch(`${API}/api/v1/products`), fetch(`${API}/api/v1/jobs`),
      ]);
      setApiOnline(health.ok);
      if (dashboard.ok) setData(await dashboard.json());
      if (productList.ok) setProducts(await productList.json());
      if (jobList.ok) setJobs(await jobList.json());
    } catch { setApiOnline(false); setNotice("Não foi possível conectar à API. Confira o endereço do backend no Render."); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);

  async function createProduct(event) {
    event.preventDefault(); setNotice("Criando job de produção…");
    try {
      const response = await fetch(`${API}/api/v1/factory/produce`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Falha ao criar job");
      setNotice(`Job criado: ${body.job_id}. Acompanhe o progresso em Jobs.`); setTopic(""); setView("Jobs"); refresh();
    } catch (error) { setNotice(error.message); }
  }
  async function sendChat(event) {
    event.preventDefault(); const text = chatInput.trim(); if (!text) return;
    setChat(items => [...items, { role: "user", text }]); setChatInput("");
    try { const response = await fetch(`${API}/api/v1/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) }); const body = await response.json(); setChat(items => [...items, { role: "assistant", text: response.ok ? body.response : body.detail || "Hermes não respondeu." }]); }
    catch { setChat(items => [...items, { role: "assistant", text: "Não consegui alcançar a API agora. Verifique o status do backend." }]); }
  }
  const completed = useMemo(() => jobs.filter(job => job.status === "completed").length, [jobs]);
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">H</div><div><strong>HERMES</strong><span>PRO / COMMAND CENTER</span></div></div><div className="live-pill"><i className={apiOnline ? "online" : "offline"}></i>{apiOnline ? "SISTEMA ONLINE" : "API INDISPONÍVEL"}</div><nav>{nav.map(([icon, label]) => <button key={label} className={view === label ? "selected" : ""} onClick={() => setView(label)}><b>{icon}</b>{label}</button>)}</nav><div className="sidebar-foot"><span>v0.2 • foundation</span><button onClick={refresh}>↻ Atualizar dados</button></div></aside>
    <main className="main"><header className="topbar"><div><span className="kicker">MÁQUINA DE PRODUTOS DIGITAIS</span><h1>{view}</h1></div><div className="top-actions"><span className="api-label"><i className={apiOnline ? "online" : "offline"}></i> {apiOnline ? "API conectada" : "Aguardando API"}</span><button className="icon-button" title="Atualizar" onClick={refresh}>↻</button><button className="avatar">W</button></div></header>{notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}{loading && <div className="loading-line"><i></i> sincronizando estado real…</div>}
      {view === "Início" && <Home data={data} products={products} jobs={jobs} completed={completed} go={setView} />}
      {view === "Hermes" && <Chat chat={chat} input={chatInput} setInput={setChatInput} send={sendChat} />}
      {view === "Fábrica" && <Factory topic={topic} setTopic={setTopic} submit={createProduct} />}
      {view === "Produtos" && <Products items={products} />}
      {view === "Jobs" && <Jobs items={jobs} />}
      {view === "Radar" && <Unavailable title="Radar de oportunidades" text="A tabela hermes_opportunity_scores existe no Supabase. A tela exibirá somente sinais analisados e persistidos quando o agente Radar estiver conectado." />}
      {view === "Vendas" && <Unavailable title="Vendas reais" text="Nenhuma venda é inventada. Esta área será preenchida por eventos confirmados da Hotmart após o webhook ser configurado." />}
      {view === "Analytics" && <Unavailable title="Analytics" text="Métricas aparecerão a partir dos eventos reais de vendas e produção. Ainda não há dados confirmados para calcular receita." />}
      {view === "Agentes" && <Agents />}
      {view === "Guias" && <Guides />}
    </main></div>
}
function Home({ data, products, jobs, completed, go }) { return <><section className="hero"><div><span className="kicker violet">HERMES PRO / LIVE OPS</span><h2>Transforme uma ideia<br /><em>em um produto.</em></h2><p>Converse com Hermes, acompanhe a fábrica e tome decisões com dados reais.</p><button className="primary" onClick={() => go("Fábrica")}>＋ Criar novo produto</button></div><div className="hero-orbit"><div className="orbit-center">H<span>AI</span></div><div className="orbit-dot dot-one">✦</div><div className="orbit-dot dot-two">◈</div><div className="orbit-dot dot-three">↗</div></div></section><section className="metric-grid"><Metric label="Produtos" value={data.products} hint="persistidos" /><Metric label="Jobs ativos" value={data.running} hint="em processamento" tone="violet" /><Metric label="Concluídos" value={completed} hint="confirmados" tone="green" /><Metric label="Falhas" value={data.failures} hint="exigem atenção" tone={data.failures ? "red" : ""} /></section><div className="section-heading"><div><span className="kicker">VISÃO OPERACIONAL</span><h3>O que está acontecendo</h3></div><button className="text-button" onClick={() => go("Jobs")}>Ver todos os jobs →</button></div><section className="two-col"><div className="panel process-panel"><div className="panel-title"><span>Product Loop</span><small>fluxo da fábrica</small></div><div className="loop"><Step icon="⌁" label="Radar" state="standby" /><span className="connector"></span><Step icon="✦" label="Estratégia" state="standby" /><span className="connector"></span><Step icon="✎" label="Conteúdo" state={data.running ? "active" : "standby"} /><span className="connector"></span><Step icon="✓" label="Quality" state="standby" /><span className="connector"></span><Step icon="↗" label="Oferta" state="standby" /></div><p className="panel-note">Nenhuma etapa é marcada como concluída sem confirmação do backend.</p></div><div className="panel health-panel"><div className="panel-title"><span>System health</span><small>estado verificado</small></div><Health label="API" ok={true} /><Health label="Database" ok={apiOnline} /><Health label="AI Gateway" ok={apiOnline} /><Health label="Worker" ok={data.worker === "ready" || data.worker === "configured"} /><Health label="Sales" ok={false} text="não configurado" /></div></section><div className="section-heading"><div><span className="kicker">RECENTES</span><h3>Últimos produtos</h3></div><button className="text-button" onClick={() => go("Produtos")}>Abrir catálogo →</button></div>{products.length ? <div className="product-row">{products.slice(0, 3).map(product => <ProductCard key={product.id} product={product} />)}</div> : <Empty icon="◈" text="Sua primeira ideia ainda está esperando." action="Criar produto" onClick={() => go("Fábrica")} />}</> }
function Metric({ label, value, hint, tone = "" }) { return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article> }
function Step({ icon, label, state }) { return <div className={`step ${state}`}><b>{icon}</b><span>{label}</span></div> }
function Health({ label, ok, text }) { return <div className="health"><span><i className={ok ? "online" : "offline"}></i>{label}</span><small>{text || (ok ? "online" : "indisponível")}</small></div> }
function Chat({ chat, input, setInput, send }) { return <section className="chat-page"><div className="chat-intro"><span className="kicker violet">HERMES / CONVERSATION</span><h2>O que vamos construir hoje?</h2><p>Peça análise, crie um job ou pergunte sobre a operação.</p></div><div className="chat-window">{chat.length ? chat.map((item, i) => <div className={`bubble ${item.role}`} key={i}><span>{item.role === "user" ? "Você" : "Hermes"}</span><p>{item.text}</p></div>) : <div className="chat-empty"><div className="spark">✦</div><h3>Olá. Eu sou Hermes.</h3><p>Posso ajudar a analisar uma ideia, iniciar uma produção ou explicar o estado do sistema.</p><div className="suggestions"><button onClick={() => setInput("Como está a saúde da operação?")}>Como está a saúde?</button><button onClick={() => setInput("Analise uma oportunidade de ebook para pequenos negócios")}>Analisar oportunidade</button></div></div>}<form className="chat-form" onSubmit={send}><input value={input} onChange={e => setInput(e.target.value)} placeholder="Fale com Hermes…" maxLength="4000" /><button className="primary">Enviar ↗</button></form></div></section> }
function Factory({ topic, setTopic, submit }) { return <section className="factory-page"><div className="page-intro"><span className="kicker violet">PRODUCT FACTORY</span><h2>Da ideia ao produto.</h2><p>O pipeline organiza estratégia, conteúdo, revisão e documento. O worker continua o trabalho sem bloquear seu navegador.</p></div><form className="factory-form" onSubmit={submit}><label>Qual produto você quer criar?<textarea value={topic} onChange={e => setTopic(e.target.value)} placeholder="Ex.: um guia prático de marketing digital para MEIs iniciantes" required minLength="3" /></label><div className="form-footer"><span>✦ Hermes vai estruturar o job</span><button className="primary">Iniciar fábrica ↗</button></div></form><div className="pipeline"><span>IDEIA</span><i>→</i><span>ESTRATÉGIA</span><i>→</i><span>CONTEÚDO</span><i>→</i><span>QUALITY</span><i>→</i><span>PDF / OFERTA</span></div></section> }
function Products({ items }) { return <section className="page"><div className="page-intro"><span className="kicker violet">CATÁLOGO</span><h2>Seus produtos</h2><p>Somente produtos retornados pela API e persistidos no banco.</p></div>{items.length ? <div className="product-grid">{items.map(product => <ProductCard key={product.id} product={product} detailed />)}</div> : <Empty icon="◈" text="Nenhum produto persistido ainda." />}</section> }
function ProductCard({ product, detailed = false }) { const metadata = product.metadata || {}; return <article className={`product-card ${detailed ? "detailed" : ""}`}><div className="cover-placeholder"><span>H</span><small>{product.status || "draft"}</small></div><div className="product-info"><span className="tag">EBOOK</span><h4>{product.title || product.topic || "Produto sem título"}</h4><p>{product.topic || "Sem descrição registrada."}</p><div className="product-meta"><span>{metadata.document_path ? "PDF salvo" : "documento pendente"}</span><span>{metadata.quality_score ? `${metadata.quality_score}/100` : "qualidade pendente"}</span></div></div></article> }
function Jobs({ items }) { return <section className="page"><div className="page-intro"><span className="kicker violet">ORCHESTRATION</span><h2>Jobs da fábrica</h2><p>Estados reais, sem sucesso falso.</p></div>{items.length ? <div className="job-list">{items.map(job => <article className="job" key={job.id}><div className={`job-icon ${job.status}`}>{job.status === "completed" ? "✓" : job.status === "failed" ? "!" : "↻"}</div><div><strong>{job.job_type}</strong><p>{job.id}</p></div><span className={`job-status ${job.status}`}>{job.status}</span><small>{job.attempts || 0} tentativas</small></article>)}</div> : <Empty icon="⚗" text="Nenhum job criado ainda." />}</section> }
function Agents() { const agents = [["RADAR", "Encontrar oportunidades", "⌁"], ["STRATEGIST", "Definir produto e oferta", "✦"], ["WRITER", "Produzir conteúdo", "✎"], ["EDITOR", "Revisar e pontuar", "✓"], ["DESIGNER", "Preparar apresentação", "◇"], ["PUBLISHER", "Preparar publicação", "↗"], ["GUARDIAN", "Detectar erros", "◉"]]; return <section className="page"><div className="page-intro"><span className="kicker violet">AGENT SYSTEM</span><h2>Agentes Hermes</h2><p>Capacidades registradas na arquitetura. Um agente só aparece como ativo quando existe execução real.</p></div><div className="agent-grid">{agents.map(([name, desc, icon]) => <article className="agent" key={name}><b>{icon}</b><div><strong>{name}</strong><p>{desc}</p></div><span className="agent-state">standby</span></article>)}</div></section> }
function Guides() { return <section className="page"><div className="page-intro"><span className="kicker violet">KNOWLEDGE BASE</span><h2>Guias do Hermes</h2><p>Como operar cada parte sem depender de conhecimento técnico.</p></div><div className="guide-grid"><Guide title="Comece aqui" text="Use Hermes para conversar ou abra Fábrica para transformar uma ideia em job. Acompanhe o estado em Jobs." /><Guide title="Produto e PDF" text="Um produto só aparece no catálogo após a API persistir o registro. O PDF só é indicado quando o Storage confirma o upload." /><Guide title="Dados reais" text="Vendas, receita e analytics não mostram números de exemplo. Eles ficam indisponíveis até existir uma integração confirmada." /><Guide title="Integrações" text="Secrets ficam somente no Render. Nunca coloque GEMINI_API_KEY, SUPABASE_SECRET_KEY ou tokens no frontend." /></div></section> }
function Guide({ title, text }) { return <article className="guide"><span>✦</span><h3>{title}</h3><p>{text}</p></article> }
function Unavailable({ title, text }) { return <section className="page"><div className="unavailable"><div className="lock">◌</div><span className="kicker violet">EM PREPARAÇÃO</span><h2>{title}</h2><p>{text}</p><span className="truth">Estado: sem dados confirmados</span></div></section> }
function Empty({ icon, text, action, onClick }) { return <div className="empty"><span>{icon}</span><h3>{text}</h3>{action && <button className="primary" onClick={onClick}>{action}</button>}</div> }
createRoot(document.getElementById("root")).render(<App />);
