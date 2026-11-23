import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function Home() {
  const supabase = await createClient();
  const { data: { claims } } = await supabase.auth.getClaims();
  if (!claims) redirect("/login");

  const userId = String(claims.sub);
  const { data: jobs } = await supabase
    .from("jobs")
    .select("id,title,platform,budget_min,budget_max,currency,score,status,technologies,url,created_at")
    .eq("owner_id", userId)
    .order("score", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false })
    .limit(30);

  const rows = jobs ?? [];
  const newJobs = rows.filter((j) => j.status === "new").length;
  const proposalReady = rows.filter((j) => j.status === "proposal_ready").length;
  const won = rows.filter((j) => j.status === "won").length;

  return (
    <main className="shell">
      <div className="container">
        <header className="header">
          <div>
            <div className="brand">JOB HUNTER</div>
            <div className="muted">Radar de oportunidades para o seu agente de desenvolvimento.</div>
          </div>
          <form action="/auth/signout" method="post"><button className="button">Sair</button></form>
        </header>

        <section className="grid">
          <div className="card"><div className="muted">Oportunidades</div><div className="metric">{rows.length}</div></div>
          <div className="card"><div className="muted">Novas</div><div className="metric">{newJobs}</div></div>
          <div className="card"><div className="muted">Propostas prontas</div><div className="metric">{proposalReady}</div></div>
          <div className="card"><div className="muted">Ganhos</div><div className="metric">{won}</div></div>
        </section>

        <div className="toolbar">
          <div><strong>Radar</strong><div className="muted">Jobs ordenados pelo score do agente.</div></div>
          <button className="button">Rodar análise</button>
        </div>

        <section className="jobs">
          {rows.length === 0 ? (
            <div className="card"><strong>Nenhuma oportunidade ainda.</strong><p className="muted">O próximo módulo conecta as fontes e começa a alimentar este painel.</p></div>
          ) : rows.map((job) => (
            <article className="card job" key={job.id}>
              <div>
                <h3>{job.title}</h3>
                <div className="muted">{job.platform ?? "Fonte manual"} · {job.currency} {job.budget_min ?? "?"}–{job.budget_max ?? "?"}</div>
                <div className="badges">{(job.technologies ?? []).map((t: string) => <span className="badge" key={t}>{t}</span>)}</div>
              </div>
              <div>
                <div className="score">{job.score ?? "—"}</div>
                {job.url && <a className="muted" href={job.url} target="_blank">Abrir job</a>}
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}