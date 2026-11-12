from __future__ import annotations

import json
from typing import Any

from ..ai_gateway.factory import build_ai_gateway
from ..core.config import Settings


SPECIALISTS: tuple[tuple[str, str], ...] = (
    ("Hermes Radar", "Analise sinais, oportunidades, riscos e lacunas de informação. Não invente dados de mercado, fontes ou validações."),
    ("Hermes Factory", "Transforme a tarefa em uma solução ou produto digital executável. Defina entregáveis, critérios de qualidade e dependências reais."),
    ("Hermes Dev", "Analise arquitetura, integrações, falhas técnicas e testes. Não afirme que executou alterações que não foram realizadas."),
    ("Hermes Analyst", "Avalie custos, riscos, retorno, métricas e viabilidade. Separe fatos, hipóteses e informações ausentes."),
    ("Hermes Designer", "Defina estrutura editorial, hierarquia visual, legibilidade, identidade da capa e ilustrações. Não declare arquivos gerados sem validação binária."),
    ("Hermes Auditor", "Aplique critérios de qualidade, segurança, integridade de arquivos, rastreabilidade e conformidade. Bloqueie publicação quando faltar evidência."),
    ("Hermes Executor", "Converta decisões aprovadas em tarefas persistentes, idempotentes e verificáveis. Não execute publicação, gastos ou ações irreversíveis sem aprovação humana."),
    ("Hermes Comercial", "Prepare oferta, descrição, público, preço como proposta e checkout. Nunca invente checkout, preço aprovado ou publicação."),
    ("Hermes Rentabilidade", "Calcule receita líquida, taxas, comissões, custos e margem usando valores documentados. Se faltar dado, retorne desconhecido em vez de estimar como fato."),
    ("Hermes Sentinel", "Analise health checks, heartbeats, incidentes e tarefas órfãs. Separe falhas detectadas, ações executadas e resultado confirmado."),
)


async def run_chief(input_text: str, settings: Settings) -> dict[str, Any]:
    """Run ten specialist perspectives and the Chief synthesis in one provider request."""
    provider = settings.ai_provider.strip().lower()
    if provider == "stub":
        raise RuntimeError("AI_PROVIDER=stub is not a production AI provider")

    primary_key_available = (
        (provider == "gemini" and bool(settings.gemini_api_key or settings.ai_api_key))
        or (provider == "openai" and bool(settings.openai_api_key))
        or (provider == "groq" and bool(settings.groq_api_key))
    )
    fallback = settings.ai_fallback_provider.strip().lower()
    fallback_key_available = (
        (fallback == "gemini" and bool(settings.gemini_api_key or settings.ai_api_key))
        or (fallback == "openai" and bool(settings.openai_api_key))
        or (fallback == "groq" and bool(settings.groq_api_key))
    )
    if not primary_key_available and not fallback_key_available:
        raise RuntimeError("Configure ao menos uma credencial de IA entre o provedor principal e o fallback")

    gateway = build_ai_gateway(settings)
    role_brief = "\n".join(f"- {name}: {instructions}" for name, instructions in SPECIALISTS)
    prompt = (
        "TAREFA ORIGINAL DO USUÁRIO:\n"
        f"{input_text}\n\n"
        "EQUIPE ESPECIALISTA — produza uma análise separada para cada papel abaixo.\n"
        f"{role_brief}\n\n"
        "Depois, Hermes Chefe deve reconciliar divergências, priorizar riscos e produzir uma síntese executável. "
        "Use fatos fornecidos, marque hipóteses e lacunas. Não afirme que ações externas foram executadas sem evidência. "
        "Não publique, compre, cobre, saque, altere preços ou execute ações irreversíveis sem autorização humana explícita.\n\n"
        "Responda estritamente como JSON válido, sem markdown, neste formato: "
        '{"specialists":{"Hermes Radar":"...","Hermes Factory":"...","Hermes Dev":"...","Hermes Analyst":"...","Hermes Designer":"...","Hermes Auditor":"...","Hermes Executor":"...","Hermes Comercial":"...","Hermes Rentabilidade":"...","Hermes Sentinel":"..."},"synthesis":"..."} '
        "Cada especialista deve entregar uma análise curta e concreta, não apenas repetir a tarefa."
    )
    response = await gateway.complete(
        prompt,
        system=(
            "Você é Hermes Chefe. Coordene dez especialistas em uma única execução estruturada. "
            "Mantenha as análises individuais separadas por nome e finalize com uma síntese objetiva. "
            "Precisão, rastreabilidade e segurança são obrigatórias."
        ),
    )
    try:
        parsed = json.loads(response.content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("O provedor de IA retornou JSON inválido para a equipe Hermes") from exc

    specialists = parsed.get("specialists") if isinstance(parsed, dict) else None
    synthesis = parsed.get("synthesis") if isinstance(parsed, dict) else None
    if not isinstance(specialists, dict) or not isinstance(synthesis, str) or not synthesis.strip():
        raise RuntimeError("Resposta da equipe Hermes incompleta: faltam specialists ou synthesis")

    findings: dict[str, str] = {}
    missing: list[str] = []
    for name, _instructions in SPECIALISTS:
        value = specialists.get(name)
        if not isinstance(value, str) or not value.strip():
            missing.append(name)
        else:
            findings[name] = value.strip()
    if missing:
        raise RuntimeError("Resposta da equipe Hermes incompleta; especialistas ausentes: " + ", ".join(missing))

    return {
        "output": synthesis.strip(),
        "agent": "Hermes Chefe",
        "steps": len(SPECIALISTS) + 1,
        "model_calls": 1,
        "specialists": findings,
        "provider": response.provider,
        "model": response.model,
    }
