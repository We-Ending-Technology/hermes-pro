export function getProductAssets(product = {}) {
  const metadata = product.metadata || {};
  const assets = metadata.assets || {};
  return {
    pdf: assets.pdf?.url || metadata.pdf_url || "",
    docx: assets.docx?.url || metadata.document_url || "",
    cover: assets.cover?.url || metadata.cover_url || metadata.active_cover?.url || "",
  };
}

export function getEditableContent(product = {}) {
  const content = product.metadata?.content;
  return content && typeof content === "object"
    ? content
    : { introduction: "", chapters: [], conclusion: "" };
}
