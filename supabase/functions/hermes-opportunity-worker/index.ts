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

async function callApi(path: string, secret: string, method = "POST") {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(API_URL + path, {
      method,
      headers: { "content-type": "application/json", "x-hermes-scheduler": secret },
      signal: controller.signal
    });
    const body = await res.text();
    if (!res.ok) throw new Error(`Hermes API ${res.status}: ${body.slice(0, 500)}`);
    return body ? JSON.parse(body) : {};
  } finally {
    clearTimeout(timer);
  }
}

async function analyzeWithAI(job: any) {
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
    "Responda objetivamente com fit, esforço, risco, valor estimado, prioridade e próxima ação.",
    "A candidatura automática é PROIBIDA quando application_automation_allowed=false.",
    JSON.stringify(compact)
  ].join("\n");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 7000);
  const res = await fetch(API_URL + "/api/v1/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message: prompt }),
    signal: controller.signal
  }).finally(() => clearTimeout(timer));
  if (!res.ok) throw new Error(`AI API HTTP ${res.status}`);
  return await res.json();
}

function estimateHours(job: any) {
  const text = `${job.title || ""} ${job.description || ""} ${(job.tags || []).join(" ")}`.toLowerCase();
  let hours = 8;
  if (/(bug|fix|erro|debug)/.test(text)) hours = 5;
  if (/(report|relatório|analysis|análise|data)/.test(text)) hours = Math.max(hours, 8);
  if (/(api|integration|integração|automation|automação|workflow)/.test(text)) hours = Math.max(hours, 12);
  if (/(dashboard|full.?stack|web app|saas|platform|plataforma)/.test(text)) hours = Math.max(hours, 20);
  if (/(ai|ia|machine learning|llm|agent|agente)/.test(text)) hours = Math.max(hours, 16);
  if (/(senior|architect|architecture|arquitetura)/.test(text)) hours = Math.max(hours, 24);
  return Math.min(hours, 60);
}

function suggestedPrice(job: any, hours: number) {
  const text = `${job.title || ""} ${job.description || ""}`.toLowerCase();
  const budget = Number(job.budget || job.salary_max || 0);
  const rate = 70;
  let price = Math.max(120, Math.round((hours * rate * 1.15) / 50) * 50);
  if (budget > 0 && budget >= price) price = Math.min(budget, price);
  const low = Math.max(100, Math.round((price * 0.9) / 50) * 50);
  const high = Math.round((price * 1.2) / 50) * 50;
  return {
    currency: "BRL",
    recommended: price,
    range: { min: low, max: high },
    basis: `${hours}h estimadas × R$ ${rate}/h + 15% de margem para escopo/risco`,
    budget_detected: budget || null,
    note: "Valor sugerido; revisar antes do envio."
  };
}

function requiredFiles(job: any) {
  const text = `${job.title || ""} ${job.description || ""} ${(job.tags || []).join(" ")}`.toLowerCase();
  const files = [
    "README.md com escopo, instalação e uso",
    ".env.example sem segredos",
    "Código-fonte do entregável",
    "Checklist de requisitos e critérios de aceite"
  ];
  if (/(api|integration|integração|backend|fastapi|python)/.test(text)) files.push("Documentação da API e exemplos de requisição");
  if (/(dashboard|web|frontend|react|site)/.test(text)) files.push("Screenshots ou link do ambiente de demonstração");
  if (/(bug|fix|debug|test|qa|teste)/.test(text)) files.push("Relatório de testes e evidências da correção");
  if (/(data|analysis|análise|report|relatório|excel|csv)/.test(text)) files.push("Relatório final e arquivo de dados/exportação, quando aplicável");
  if (/(ai|ia|llm|machine learning|agent|agente)/.test(text)) files.push("Descrição da arquitetura do fluxo de IA e limites conhecidos");
  return [...new Set(files)];
}

function checklist(job: any) {
  const text = `${job.title || ""} ${job.description || ""}`.toLowerCase();
  const items = [
    "Ler o anúncio completo e confirmar escopo",
    "Confirmar prazo e formato de entrega",
    "Confirmar acesso, credenciais e materiais necessários",
    "Validar requisitos obrigatórios e critérios de aceite",
    "Testar o entregável antes da submissão",
    "Revisar preço e prazo sugeridos",
    "Revisar a proposta para remover qualquer afirmação não comprovada",
    "Submeter somente pelo canal oficial da plataforma"
  ];
  if (/(api|integration|integração)/.test(text)) items.splice(4, 0, "Validar endpoints, autenticação, limites e ambiente de teste");
  if (/(data|analysis|report|relatório)/.test(text)) items.splice(4, 0, "Validar origem dos dados, cálculos e formato do relatório");
  if (/(bug|fix|debug)/.test(text)) items.splice(4, 0, "Reproduzir o problema antes da correção e registrar evidência");
  return items;
}

function proposalText(job: any, hours: number, price: any) {
  const title = String(job.title || "projeto");
  return [
    "Olá!",
    "",
    `Vi o projeto "${title}" e consigo estruturar a execução em etapas objetivas, começando pela validação do escopo e dos requisitos.`,
    "",
    "Minha proposta inicial é:",
    `• Entender e validar o escopo: requisitos, entradas, saídas e critérios de aceite.`,
    `• Implementar o que foi solicitado com foco em organização, testes e documentação.`,
    `• Entregar os arquivos e evidências necessários para validação.`,
    "",
    `Estimativa inicial: ${hours} horas.`,
    `Valor sugerido: R$ ${price.recommended.toFixed(2).replace(".", ",")} (ajustável após confirmar o escopo).`,
    "",
    "Antes de iniciar, confirmaria apenas os acessos, materiais de referência, prazo e critérios de aceite do projeto.",
    "",
    "Se o escopo estiver alinhado, posso começar pela primeira etapa e apresentar o resultado para validação."
  ].join("\n");
}

function buildProposal(job: any, ai: any | null) {
  const hours = estimateHours(job);
  const price = suggestedPrice(job, hours);
  const files = requiredFiles(job);
  const checks = checklist(job);
  return {
    status: "ready_for_review",
    generated_at: new Date().toISOString(),
    title: `Proposta — ${job.title || "oportunidade"}`,
    suggested_price: price,
    estimated_hours: hours,
    proposal_text: proposalText(job, hours, price),
    required_files: files,
    checklist: checks,
    automation: {
      discovery_allowed: job.discovery_automation_allowed === true,
      application_allowed: job.application_automation_allowed === true,
      submission_status: job.application_automation_allowed === true ? "eligible_for_official_adapter_review" : "manual_submission_required"
    },
    ai_analysis: ai ? {
      provider: ai.provider || null,
      model: ai.model || null,
      response: ai.response || "",
      generated_at: new Date().toISOString()
    } : null,
    claims_policy: "Não afirmar experiência, portfólio, prazo ou resultado que não estejam comprovados."
  };
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
      const proposal = buildProposal(job.payload || {}, null);

      await supabase.from("hermes_jobs").update({
        status: "manual_submission_required",
        payload: {
          ...(job.payload || {}),
          proposal,
          next_action: "review_proposal_and_submit_manually"
        },
        error_message: null,
        updated_at: new Date().toISOString()
      }).eq("id", job.id);

      let ai = null;
      try { ai = await analyzeWithAI(job.payload || {}); } catch (_) {}

      const enrichedProposal = buildProposal(job.payload || {}, ai);
      const nextStatus = job.payload?.application_automation_allowed === true
        ? "proposal_ready"
        : "manual_submission_required";

      const payload = {
        ...(job.payload || {}),
        proposal,
        next_action: nextStatus === "manual_submission_required"
          ? "review_proposal_and_submit_manually"
          : "review_proposal_and_use_official_adapter"
      };

      const finalPayload = { ...payload, proposal: enrichedProposal };
      await supabase.from("hermes_jobs").update({
        status: nextStatus,
        payload: finalPayload,
        error_message: null,
        updated_at: new Date().toISOString()
      }).eq("id", job.id);

      if (nextStatus === "proposal_ready" && job.payload?.source === "freelancer") {
        try {
          await callApi(`/api/v1/autonomy/freelancer/apply/${job.id}`, expected);
        } catch (e) {
          await supabase.from("hermes_jobs").update({
            status: "proposal_ready",
            error_message: e instanceof Error ? e.message : String(e),
            updated_at: new Date().toISOString()
          }).eq("id", job.id);
        }
      }

      if (job.payload?.source && job.payload?.url) {
        await supabase.from("hermes_opportunities")
          .update({ status: "proposal_ready", metadata: { proposal } })
          .eq("source", job.payload.source)
          .eq("source_url", job.payload.url);
      }
      processed++;
    } catch (e) {
      failed++;
      const message = e instanceof Error ? e.message : String(e);
      const terminal = attempts >= Number(job.max_attempts || 3);
      await supabase.from("hermes_jobs").update({
        status: terminal ? "failed" : "pending",
        attempts,
        error_message: message,
        updated_at: new Date().toISOString()
      }).eq("id", job.id);
    }
  }

  let contractSync: any = null;
  let executions: any[] = [];
  try {
    contractSync = await callApi("/api/v1/autonomy/freelancer/sync", expected);
    const { data: executionJobs } = await supabase
      .from("hermes_jobs")
      .select("id,status,payload,attempts,max_attempts")
      .eq("job_type", "service_execution")
      .eq("status", "pending")
      .order("created_at", { ascending: true })
      .limit(3);
    for (const executionJob of executionJobs || []) {
      try {
        executions.push(await callApi(`/api/v1/autonomy/jobs/${executionJob.id}/execute`, expected));
      } catch (e) {
        executions.push({ job_id: executionJob.id, error: e instanceof Error ? e.message : String(e) });
      }
    }
  } catch (e) {
    contractSync = { error: e instanceof Error ? e.message : String(e) };
  }

  return Response.json({ ok: true, processed, failed, contract_sync: contractSync, executions });
});
