import StatusBadge from "../components/StatusBadge";
import { getProductAssets } from "../lib/productWorkspace";

function ProductCard({ product, onSelect }) {
  const metadata = product.metadata || {};
  const assets = getProductAssets(product);
  const quality = metadata.quality_gate || {};
  const marketing = metadata.marketing_pack || {};
  const coverArt = metadata.cover_art || {};
  const ready = product.status === "ready_to_publish"
    && quality.approved === true
    && coverArt.generated === true
    && metadata.marketing_pack_status === "ready";

  return <article className="product-card detailed">
    <div className="cover-placeholder" style={{ overflow: "hidden", minHeight: 180 }}>
      {assets.cover
        ? <img src={assets.cover} alt={`Capa de ${product.title || product.topic}`} style={{ width: "100%", height: 220, objectFit: "cover", display: "block" }} />
        : <span>{(product.title || product.topic || "H").slice(0, 1)}</span>}
    </div>
    <div className="product-info">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span className="tag">{product.current_stage || "produto"}</span>
        <StatusBadge status={product.status} />
      </div>
      <h3>{product.title || product.topic}</h3>
      <p>{product.topic}</p>
      <div className="panel-note">
        <b>Qualidade:</b> {quality.approved ? "aprovado" : "aguardando revisão"}
        {quality.page_count != null && ` · ${quality.page_count} páginas`}
        {quality.word_count != null && ` · ${quality.word_count.toLocaleString("pt-BR")} palavras`}
        {quality.illustration_count != null && ` · ${quality.illustration_count} ilustrações`}
      </div>
      <div className="panel-note">
        <b>Capa IA:</b> {coverArt.generated ? `${coverArt.provider || "IA"} · ${coverArt.model || "modelo"}` : "pendente"}
        {" · "}
        <b>Texto comercial:</b> {metadata.marketing_pack_status === "ready" && marketing.product_description ? "pronto" : "pendente"}
      </div>
      {marketing.short_description && <p>{marketing.short_description}</p>}
      <div className="asset-actions">
        {assets.pdf && <a href={assets.pdf} target="_blank" rel="noreferrer">PDF ↗</a>}
        {assets.docx && <a href={assets.docx} target="_blank" rel="noreferrer">DOCX ↗</a>}
        {assets.cover && <a href={assets.cover} target="_blank" rel="noreferrer">Capa ↗</a>}
      </div>
      <div className="form-footer">
        <span>{ready ? "Apto para vincular checkout" : "Ainda não liberado para venda"}</span>
        <button className="secondary" onClick={() => onSelect(product)}>Abrir Studio</button>
      </div>
    </div>
  </article>;
}

export default function Products({ items = [], select }) {
  return <section className="panel">
    <div className="section-head">
      <div><span className="kicker">PRODUCT STUDIO</span><h2>Produtos</h2></div>
      <span className="panel-note">{items.length} produto(s) persistidos</span>
    </div>
    {items.length === 0
      ? <div className="empty"><strong>Nenhum produto ainda.</strong><p>O Hermes criará o job e exibirá o estado real de produção.</p></div>
      : <div className="product-grid">
          {items.map(product => <ProductCard key={product.id} product={product} onSelect={select} />)}
        </div>}
  </section>;
}
