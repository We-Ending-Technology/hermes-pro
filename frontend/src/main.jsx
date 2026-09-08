import React from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

function App() {
  return <main className="shell"><header><span className="eyebrow">HERMES PRO</span><h1>AI Product Factory</h1><p>Fundação operacional para produtos e automações orientados por agentes.</p></header><section className="grid"><article><span className="label">STATUS</span><strong>Foundation ready</strong><p>API, gateway de IA, agentes e worker separados.</p></article><article><span className="label">NEXT</span><strong>Connect your workspace</strong><p>Integrações de marketplaces serão adicionadas em uma próxima etapa.</p></article></section></main>
}

createRoot(document.getElementById("root")).render(<App />);
