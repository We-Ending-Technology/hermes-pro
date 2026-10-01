from __future__ import annotations

from typing import Any

from agents import Agent, Runner

from ..core.config import Settings


def build_agents(settings: Settings) -> tuple[Agent, dict[str, Agent]]:
    model = settings.openai_agent_model

    radar = Agent(
        name="Hermes Radar",
        model=model,
        instructions=(
            "You are the Hermes Radar specialist. Identify concrete opportunities, "
            "risks, missing information and next actions. Never invent market data. "
            "Return concise structured findings."
        ),
    )
    factory = Agent(
        name="Hermes Factory",
        model=model,
        instructions=(
            "You are the Hermes Factory specialist. Turn validated opportunities into "
            "digital-product specifications, outlines, production steps and quality gates. "
            "Do not claim a product was published unless a real tool confirms it."
        ),
    )
    developer = Agent(
        name="Hermes Dev",
        model=model,
        instructions=(
            "You are the Hermes Dev specialist. Diagnose software problems, propose "
            "safe implementation steps and identify tests. Never claim code was changed "
            "unless the connected tool actually changed it."
        ),
    )
    analyst = Agent(
        name="Hermes Analyst",
        model=model,
        instructions=(
            "You are the Hermes Analyst specialist. Analyze costs, execution risk, "
            "quality and measurable outcomes. Separate facts, assumptions and unknowns."
        ),
    )

    chief = Agent(
        name="Hermes Chefe",
        model=model,
        instructions=(
            "You are the chief orchestrator of Hermes Pro. Keep ownership of the final "
            "result. Delegate research, product, development and analysis work to the "
            "specialists when useful. Never invent completed actions. For risky external "
            "actions, require human approval. Produce a concise action plan, current "
            "state, evidence and next step."
        ),
        tools=[
            radar.as_tool(
                tool_name="radar_specialist",
                tool_description="Research and structure an opportunity or operational signal.",
            ),
            factory.as_tool(
                tool_name="factory_specialist",
                tool_description="Design a digital product and its production workflow.",
            ),
            developer.as_tool(
                tool_name="dev_specialist",
                tool_description="Diagnose or plan a safe software implementation.",
            ),
            analyst.as_tool(
                tool_name="analyst_specialist",
                tool_description="Analyze economics, quality, risks and measurable outcomes.",
            ),
        ],
    )
    return chief, {
        "radar": radar,
        "factory": factory,
        "dev": developer,
        "analyst": analyst,
        "chief": chief,
    }


async def run_chief(input_text: str, settings: Settings) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for autonomous agents")
    chief, _ = build_agents(settings)
    result = await Runner.run(chief, input_text)
    return {
        "output": result.final_output,
        "agent": result.last_agent.name,
        "steps": len(result.new_items),
    }
