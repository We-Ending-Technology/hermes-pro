export default function StatusBadge({ status }) {
  const labels = { connected: "Conectado", configured: "Configurado", not_configured: "Não configurado", unavailable: "Indisponível", queued: "Na fila", running: "Executando", completed: "Concluído", failed: "Falhou", retrying: "Tentando novamente" };
  return <span className={`status status-${status}`}>{labels[status] || status}</span>;
}
