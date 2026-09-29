import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") || "{}");
const ADMIN_KEY = secretKeys["default"] || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const supabase = createClient(SUPABASE_URL, ADMIN_KEY);

const KEYWORDS = [
  "python","fastapi","api","automation","ai","artificial intelligence",
  "data","analytics","bug","testing","qa","report","dashboard",
  "backend","developer","software","integration","machine learning",
  "scraping","workflow","llm","openai","gemini"
];

function textOf(v: unknown) { return String(v ?? "").toLowerCase(); }

function scoreJob(title: string, description: string, tags: string[], salaryMax?: number) {
  const text = [title, description, ...tags].map(textOf).join(" ");
  const hits = KEYWORDS.filter(k => text.includes(k));
  let score = Math.min(75, 35 + hits.length * 4);
  if (salaryMax && salaryMax > 1000) score += 10;
  if (text.includes("senior")) score -= 8;
  if (text.includes("manager") || text.includes("director")) score -= 10;
  return { score: Math.max(0, Math.min(100, score)), hits };
}

async function getJson(url: string) {
  const res = await fetch(url, { headers: { "user-agent": "Hermes-Pro-Autonomy/1.0" } });
  if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
  return await res.json();
}

async function fetchRemoteOK() {
  const data = await getJson("https://remoteok.com/api");
  return (Array.isArray(data) ? data : []).slice(1).map((j: any) => ({
    source: "remoteok", title: j.position || j.title || "", description: j.description || "",
    url: j.url || "", external_id: String(j.id || j.url || ""),
    tags: Array.isArray(j.tags) ? j.tags : [], salary_max: Number(j.salary_max || 0) || null, raw: j
  }));
}

async function fetchRemotive() {
  const data = await getJson("https://remotive.com/api/remote-jobs?limit=100");
  return (data.jobs || []).map((j: any) => ({
    source: "remotive", title: j.title || "", description: j.description || "", url: j.url || "",
    external_id: String(j.id || j.url || ""), tags: Array.isArray(j.tags) ? j.tags : [],
    salary_max: Number(j.salary_max || 0) || null, raw: j
  }));
}

async function fetchArbeitnow() {
  const data = await getJson("https://www.arbeitnow.com/api/job-board-api");
  return (data.data || []).map((j: any) => ({
    source: "arbeitnow", title: j.title || "", description: j.description || "", url: j.url || "",
    external_id: String(j.slug || j.url || ""), tags: Array.isArray(j.tags) ? j.tags : [],
    salary_max: null, raw: j
  }));
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return Response.json({ error: "POST required" }, { status: 405 });

  const supplied = req.headers.get("x-hermes-scheduler") || "";
  const { data: expected, error: secretError } = await supabase.rpc("get_hermes_scheduler_secret");
  if (secretError || !expected || supplied !== expected) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const started = new Date().toISOString();
  const runIds: string[] = [];
  let discovered = 0;
  let accepted = 0;
  const errors: string[] = [];
  const sources = [["remoteok", fetchRemoteOK], ["remotive", fetchRemotive], ["arbeitnow", fetchArbeitnow]] as const;

  for (const [source, loader] of sources) {
    const { data: run } = await supabase
      .from("hermes_radar_runs")
      .insert({ source, status: "running", started_at: started, metadata: { scheduler: "supabase_cron" } })
      .select("id").single();

    try {
      const jobs = await loader();
      discovered += jobs.length;

      for (const job of jobs) {
        const { score, hits } = scoreJob(job.title, job.description, job.tags, job.salary_max || undefined);
        if (score < 55 || !job.url) continue;

        const idempotency = `opportunity:${source}:${job.external_id}`;
        const metadata = {
          source, external_id: job.external_id, tags: job.tags, salary_max: job.salary_max,
          matched_keywords: hits, discovery_automation_allowed: true,
          application_automation_allowed: false, discovered_at: new Date().toISOString(), raw: job.raw
        };

        const { error: oppError } = await supabase.from("hermes_opportunities").upsert({
          type: "service", title: job.title, description: job.description, source, source_url: job.url,
          signals: { matched_keywords: hits, source }, score,
          confidence: Math.min(95, 60 + hits.length * 3), status: "discovered",
          idempotency_key: idempotency, metadata
        }, { onConflict: "idempotency_key", ignoreDuplicates: true });
        if (oppError) { errors.push(`${source}:opportunity:${oppError.message}`); continue; }

        const { error: jobError } = await supabase.from("hermes_jobs").upsert({
          job_type: "opportunity_pipeline", status: "pending", attempts: 0, max_attempts: 3,
          payload: {
            source, title: job.title, url: job.url, description: job.description, tags: job.tags,
            score, confidence: Math.min(95, 60 + hits.length * 3),
            discovery_automation_allowed: true, application_automation_allowed: false,
            next_action: "analyze_and_prepare", discovered_at: new Date().toISOString()
          },
          idempotency_key: idempotency
        }, { onConflict: "idempotency_key", ignoreDuplicates: true });
        if (jobError) { errors.push(`${source}:job:${jobError.message}`); continue; }
        accepted++;
      }

      if (run?.id) {
        runIds.push(run.id);
        await supabase.from("hermes_radar_runs").update({
          status: "completed", items_found: jobs.length, finished_at: new Date().toISOString()
        }).eq("id", run.id);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      errors.push(`${source}:${message}`);
      if (run?.id) {
        runIds.push(run.id);
        await supabase.from("hermes_radar_runs").update({
          status: "failed", error_message: message, finished_at: new Date().toISOString()
        }).eq("id", run.id);
      }
    }
  }

  return Response.json({ ok: true, scheduler: "supabase_cron", discovered, accepted, runs: runIds, errors });
});
