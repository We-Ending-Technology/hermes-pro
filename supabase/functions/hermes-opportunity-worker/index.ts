import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") || "{}");
const ADMIN_KEY = secretKeys["default"] || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const supabase = createClient(SUPABASE_URL, ADMIN_KEY);
const API_URL = "https://hermes-pro-api-commercial.onrender.com";

async function schedulerSecret() {
  const { data } = await supabase.rpc("get_hermes_scheduler_secret");
  return data || "";
}

async function analyze(job: any) {
  const compact = {
    source: job.source,
    title: String(job.title || "").slice(0, 500),
    url: job.url,
    score: job.score,
    tags: Array.isArray(job.tags) ? job.tags.slice(0, 20) : [],
    description: String(job.description || "").slice(0, 2200),
    application_automation_allowed: job.application_automation_allowed === true
  };
  const prompt = [
    "Analise esta oportunidade para o pipeline Hermes.",
    "Não invente experiência, cliente, preço ou prazo.",
    "Responda de forma objetiva com fit, esforço, risco, valor estimado, prioridade e próxima ação.",
    "A candidatura automática é PROIBIDA quando application_automation_allowed=false.",
    JSON.stringify(compact)
  ].join("\n");

  const res = await fetch(API_URL + "/api/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message: prompt })
  });
  if (!res.ok) throw new Error(`AI API HTTP ${res.status}`);
  return await res.json();
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return Response.json({ error: "POST required" }, { status: 405 });
  const expected = await schedulerSecret();
  if (!expected || req.headers.get("x-hermes-scheduler") !== expected) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const { data: jobs, error } = await supabase
    .from("hermes_jobs")
    .select("id,status,attempts,max_attempts,payload,created_at")
    .eq("job_type", "opportunity_pipeline")
    .eq("status", "pending")
    .order("created_at", { ascending: true })
    .limit(5);

  if (error) return Response.json({ ok: false, error: error.message }, { status: 500 });

  let processed = 0;
  let failed = 0;

  for (const job of jobs || []) {
    const attempts = Number(job.attempts || 0) + 1;
    await supabase.from("hermes_jobs").update({
      status: "running", attempts, updated_at: new Date().toISOString()
    }).eq("id", job.id);

    try {
      const ai = await analyze(job.payload || {});
      const analysis = {
        provider: ai.provider || null,
        model: ai.model || null,
        response: ai.response || "",
        analyzed_at: new Date().toISOString()
      };
      const nextStatus = job.payload?.application_automation_allowed === true
        ? "proposal_ready" : "manual_submission_required";

      await supabase.from("hermes_jobs").update({
        status: nextStatus,
        payload: { ...(job.payload || {}), analysis, next_action: nextStatus === "manual_submission_required" ? "review_and_submit_manually" : "prepare_application" },
        error_message: null, updated_at: new Date().toISOString()
      }).eq("id", job.id);
      processed++;
    } catch (e) {
      failed++;
      const message = e instanceof Error ? e.message : String(e);
      const terminal = attempts >= Number(job.max_attempts || 3);
      await supabase.from("hermes_jobs").update({
        status: terminal ? "failed" : "pending",
        attempts, error_message: message, updated_at: new Date().toISOString()
      }).eq("id", job.id);
    }
  }

  return Response.json({ ok: true, processed, failed });
});
