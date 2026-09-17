import test from "node:test";
import assert from "node:assert/strict";
import { getProductAssets } from "./productWorkspace.js";

test("product workspace reads generated assets from the persisted metadata contract", () => {
  const assets = getProductAssets({
    metadata: {
      assets: {
        pdf: { url: "https://example.test/book.pdf" },
        docx: { url: "https://example.test/book.docx" },
        cover: { url: "https://example.test/cover.png" },
      },
    },
  });
  assert.deepEqual(assets, {
    pdf: "https://example.test/book.pdf",
    docx: "https://example.test/book.docx",
    cover: "https://example.test/cover.png",
  });
});

test("product workspace keeps legacy flat asset URLs working", () => {
  const assets = getProductAssets({ metadata: { pdf_url: "pdf", document_url: "docx", cover_url: "cover" } });
  assert.deepEqual(assets, { pdf: "pdf", docx: "docx", cover: "cover" });
});
