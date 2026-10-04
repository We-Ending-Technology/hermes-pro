import { useMemo, useState } from "react";

const DOMAIN_PATTERNS = ["Nexora","Velora","Novara","Lumora","Veyra","Solvra","Nuvora","Elvora","Zenvora","Axora","Virelo","Nexivo","Velivo","Novilo","Omnira"];
const TEST_PRODUCTS = [
  { name:"Budget Starter Kit", niche:"Personal Finance", price:9.9, revenue:127, costs:21, conversion:2.8, status:"ESCALAR" },
  { name:"7-Day Focus Planner", niche:"Productivity", price:7.9, revenue:43, costs:38, conversion:0.7, status:"TESTAR" },
  { name:"AI Prompt Toolkit", niche:"AI", price:12.9, revenue:12, costs:31, conversion:0.2, status:"MATAR" }
];
function scoreOpportunity({ demand, competition, differentiation, difficulty, pricing, clarity }) {
  return Math.round(demand*.25+(100-competition)*.15+differentiation*.2+(100-difficulty)*.15+pricing*.15+clarity*.1);
}
export default function LowTicketFactory() {
  const [brand,setBrand]=useState(""); const [niche,setNiche]=useState(""); const [problem,setProblem]=useState(""); const [price,setPrice]=useState("9.90");
  const [signals,setSignals]=useState({demand:75,competition:40,differentiation:75,difficulty:30,pricing:70,clarity:85}); const [tested,setTested]=useState(false);
  const score=useMemo(()=>scoreOpportunity(signals),[signals]); const estimatedProfit=(Number(price)||0)*.9-2;
  return <section className="page">
    <div className="page-intro"><span className="kicker violet">LOW-TICKET FACTORY / ENGLISH MARKET</span><h2>Testar produtos. Medir lucro. Escalar vencedores.</h2><p>Uma operação guarda-chuva para lançar ofertas de vários nichos em inglês sem criar um domínio novo para cada produto.</p></div>
    <div className="metric-grid">
      <article className="metric"><span>Oportunidade</span><strong>{score}/100</strong><small>score heurístico</small></article>
      <article className="metric"><span>Preço alvo</span><strong>\${price}</strong><small>low ticket</small></article>
      <article className="metric"><span>Lucro estimado</span><strong>\${estimatedProfit.toFixed(2)}</strong><small>antes de ads/refunds</small></article>
      <article className="metric"><span>Produtos em teste</span><strong>3</strong><small>exemplo operacional</small></article>
    </div>
    <div className="two-col lowticket-grid">
      <div className="panel">
        <div className="section-heading"><div><span className="kicker violet">01 / OPPORTUNITY</span><h3>Construir hipótese</h3></div></div>
        <div className="form-grid"><label>Brand guarda-chuva<input value={brand} onChange={e=>setBrand(e.target.value)} placeholder="Ex.: Nexora" /></label><label>Nicho<input value={niche} onChange={e=>setNiche(e.target.value)} placeholder="Ex.: productivity" /></label></div>
        <label>Problema em inglês<textarea value={problem} onChange={e=>setProblem(e.target.value)} placeholder="Ex.: I need a simple weekly system to stay focused..." /></label>
        <label>Preço<input type="number" min="1" step="0.01" value={price} onChange={e=>setPrice(e.target.value)} /></label>
        <div className="signal-list">{Object.entries(signals).map(([key,value])=><label key={key}><span>{key}</span><input type="range" min="0" max="100" value={value} onChange={e=>setSignals({...signals,[key]:Number(e.target.value)})}/><b>{value}</b></label>)}</div>
        <button className="primary" onClick={()=>setTested(true)}>Gerar plano de teste ↗</button>
        {tested&&<div className="lowticket-result"><b>{score>=70?"READY TO TEST":score>=55?"REFINE HYPOTHESIS":"LOW PRIORITY"}</b><p>{brand||"Sua marca"} → {niche||"general niche"} → \${price} offer.</p></div>}
      </div>
      <div className="panel">
        <div className="section-heading"><div><span className="kicker violet">02 / DOMAIN LAB</span><h3>Nomes genéricos</h3></div></div>
        <p className="panel-note">Ideias de naming. Disponibilidade do .com precisa ser verificada antes da compra.</p>
        <div className="domain-grid">{DOMAIN_PATTERNS.map(name=><button key={name} className="domain-chip" onClick={()=>setBrand(name)}>{name}.com</button>)}</div>
        <div className="domain-rules"><b>Critérios</b><span>.com · brandable · curto · sem hífen · sem nicho</span><span>Use uma marca para vários produtos; crie domínio próprio só quando houver vencedor.</span></div>
      </div>
    </div>
    <div className="section-heading"><div><span className="kicker violet">03 / PORTFOLIO</span><h3>Profit-first scoreboard</h3></div></div>
    <div className="panel table-panel"><div className="lowticket-table"><div className="table-head"><span>Produto</span><span>Nicho</span><span>Receita</span><span>Custos</span><span>Lucro</span><span>Conv.</span><span>Status</span></div>
      {TEST_PRODUCTS.map(p=><div className="table-row" key={p.name}><span><b>{p.name}</b><small>\${p.price}</small></span><span>{p.niche}</span><span>\${p.revenue}</span><span>\${p.costs}</span><span>\${p.revenue-p.costs}</span><span>{p.conversion}%</span><strong className={p.status.toLowerCase()}>{p.status}</strong></div>)}
    </div></div>
    <div className="two-col">
      <div className="panel"><span className="kicker violet">04 / DECISION ENGINE</span><h3>ESCALAR / TESTAR / MATAR</h3><p>O Hermes deve decidir pelo lucro e pelos sinais de conversão, não por faturamento isolado.</p><div className="decision-list"><span><b>ESCALAR</b> margem + conversão comprovadas</span><span><b>TESTAR</b> sinal promissor, mas gargalo identificado</span><span><b>MATAR</b> prejuízo persistente sem hipótese melhor</span></div></div>
      <div className="panel"><span className="kicker violet">05 / GRAVEYARD</span><h3>Memória dos produtos mortos</h3><p>Produtos que falharam ficam registrados com nicho, oferta, preço, tráfego, conversão e motivo da falha para evitar repetir o erro.</p><span className="truth">SEM MÉTRICAS INVENTADAS · DADOS REAIS QUANDO CONECTADOS</span></div>
    </div>
  </section>;
}