from __future__ import annotations

from typing import Any

from ..ai_gateway.factory import build_ai_gateway
from ..core.config import Settings


SPECIALISTS: tuple[tuple[str, str], ...] = (
    (
        "Hermes Radar",
        "Analise sinais, oportunidades, riscos e lacunas de informação. "
        "Não invente dados de mercado, fontes ou validações.",
    ),
    (
        "Hermes Factory",
        "Transforme a tarefa em uma solução ou produto digital executável. "
        "Defina entregáveis, critérios de qualidade e dependências reais.",
    ),
    (
        "Hermes Dev",
        "Analise arquitetura, integrações, falhas técnicas e testes. "
        "Não afirme que executou alterações que não foram realizadas.",
    ),
    (
        "Hermes Analyst",
        "Avalie custos, riscos, retorno, métricas e viabilidade. "
        "Separe fatos, hipóteses e informações ausentes.",
    ),
)


async def run_chief(input_text: str, settings: Settings) -> dict[str, Any]:
    """Run the specialist team with the configured provider, then synthesize."""
    provider = settings.ai_provider.strip().lower()
    if provider == "stub":
        raise RuntimeError("AI_PROVIDER=stub is not a production AI provider")

    if provider == "gemini" and not (settings.gemini_api_key or settings.ai_api_key):
        raise RuntimeError("GEMINI_API_KEY is required for autonomous agents")
    if provider == "openai" and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for autonomous agents")

    gateway = build_ai_gateway(settings)
    findings: dict[str, str] = {}

    for name, instructions in SPECIALISTS:
        response = await gateway.complete(
            f"Tarefa recebida do usuário:\n{input_text}\n\n"
            "Produza uma análise objetiva, com fatos, hipóteses, riscos e ações recomendadas.",
            system=f"{instructions} Você integra o time Hermes Pro. Seja conciso e verificável.",
        )
        findings[name] = response.content

    specialist_context = "\n\n".join(
        f"## {name}\n{content}" for name, content in findings.items()
    )
    final = await gateway.complete(
        f"Tarefa original:\n{input_text}\n\n"
        f"Análises dos especialistas:\n{specialist_context}\n\n"
        "Consolide as análises, resolva divergências, identifique bloqueios reais e "
        "entregue o resultado mais útil. Não declare ações como concluídas sem evidência.",
        system=(
            "Você é Hermes Chefe, responsável pelo resultado final. "
            "Coordene os especialistas, priorize segurança e execução verificável, "
            "separe fatos de inferências e não invente resultados."
        ),
    )
    return {
        "output": final.content,
        "agent": "Hermes Chefe",
        "steps": len(findings) + 1,
        "specialists": findings,
        "provider": final.provider,
        "model": final.model,
    }
