import StatusBadge from "../components/StatusBadge";
export default function Sales({ data }) {
  const orders = Number(data?.orders ?? 0);
  const hasNetSales = data?.revenue != null && orders > 0;
  const revenueLabel = data?.revenue == null
    ? "Sem dados de receita"
    : hasNetSales
      ? `R$ ${Number(data.revenue).toFixed(2)}`
      : "Nenhuma venda líquida";
  const details = hasNetSales
    ? `${orders} pedidos líquidos · ticket médio R$ ${Number(data.ticket ?? 0).toFixed(2)}`
    : "Nenhum pedido pago líquido confirmado.";
  return (
    <section className="panel">
      <span className="kicker">SALES</span>
      <h2>Vendas reais</h2>
      <div className="sales-empty">
        <StatusBadge status={data?.status || "unavailable"} />
        <strong>{revenueLabel}</strong>
        <p>{data?.message || "Nenhuma venda paga registrada ainda. O painel será atualizado quando chegar um evento real do checkout."}</p>
        <p>{details}</p>
      </div>
    </section>
  );
}
