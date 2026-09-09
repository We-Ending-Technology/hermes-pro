import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { api } from "./lib/api";
import BottomNav from "./components/BottomNav";
import Dashboard from "./views/Dashboard";
import Products from "./views/Products";
import Factory from "./views/Factory";
import Radar from "./views/Radar";
import Sales from "./views/Sales";
import Analytics from "./views/Analytics";
import Agents from "./views/Agents";

function App(){
 const [active,setActive]=useState("home"); const [dashboard,setDashboard]=useState(null); const [products,setProducts]=useState([]); const [sales,setSales]=useState(null); const [analytics,setAnalytics]=useState(null); const [agents,setAgents]=useState([]); const [error,setError]=useState(""); const [loading,setLoading]=useState(true);
 const load=async()=>{setLoading(true);setError(""); try { const [d,p,s,a,g]=await Promise.all([api.dashboard(),api.products(),api.sales(),api.analytics(),api.agents()]); setDashboard(d);setProducts(p);setSales(s);setAnalytics(a);setAgents(g.agents||[]); } catch(e){setError(e.message)} finally{setLoading(false)} };
 useEffect(()=>{load()},[]);
 const create=async(topic)=>{const value=typeof topic === "string" ? topic : window.prompt("Tema do produto:",""); if(!value?.trim()) return; try { await api.createProduct({topic:value.trim(),idempotency_key:`ui-${value.trim().toLowerCase()}`}); await load(); setActive("products"); } catch(e){setError(e.message)} };
 const view={home:<Dashboard data={dashboard} loading={loading} onCreate={create}/>,products:<Products products={products} onCreate={create}/>,factory:<Factory onCreate={create}/>,radar:<Radar apiRadar={api.radar}/>,sales:<Sales data={sales}/>,analytics:<Analytics data={analytics}/>,agents:<Agents agents={agents}/>}[active];
 return <div className="app"><header className="topbar"><div className="brand"><span className="brand-mark">H</span><div><strong>HERMES PRO</strong><small>COMMERCIAL ENGINE</small></div></div><button className="avatar" onClick={load}>↻</button></header><main>{error&&<div className="error">API: {error}</div>}{view}</main><BottomNav active={active} onChange={setActive}/></div>
}
createRoot(document.getElementById("root")).render(<App/>);
