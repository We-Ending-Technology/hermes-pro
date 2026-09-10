import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
export default function Dashboard({ data, loading, onCreate }) {
  if (loading) return <div className="panel loading">Carregando comando central…</div>;
  return <>
    <section className="hero"><div><span className="kicker">COMMAND CENTER</span><h1>Transforme uma hipótese em produto.</h1><p>O Hermes organiza pesquisa, criação, revisão e preparação comercial sem inventar dados.</p></div><button className="primary" onClick={onCreate}>+ Criar produto</button></section>
    <section className="metrics"><MetricCard label="Produtos" value={data?.products ?? 0} hint="criados nesta sessão"/><MetricCard label="Jobs ativos" value={data?.active_jobs ?? 0} hint="fila / execução"/><MetricCard label="Concluídos" value={data?.completed_products ?? 0} hint="com estado real"/><MetricCard label="Receita" value={data?.revenue == null ? "—" : `R$ ${data.revenue.toFixed(2)}`} hint={data?.revenue == null ? "aguardando Hotmart" : "dados reais"}/></section>
    <section className="panel"><div className="section-head"><div><span className="kicker">INTEGRATIONS</span><h2>Saúde operacional</h2></div></div><div className="integration-grid">{(data?.integrations || []).map(i => <div className="integration" key={i.name}><div><strong>{i.name}</strong><p>{i.message}</p></div><StatusBadge status={i.status}/></div>)}</div></section>
  </>;
}
