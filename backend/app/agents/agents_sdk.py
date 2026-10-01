from __future__ import annotations

from typing import Any

from agents import Agent, Runner


def build_chief() -> Agent:
    radar = Agent(
        name="Hermes Radar",
        instructions="Find concrete opportunities and operational signals. Separate evidence from assumptions.",
        model="gpt-6-astra",
    )
    analyst = Agent(
        name="Hermes Analyst",
        instructions="Analyze costs, risk, feasibility and measurable outcomes. Do not invent facts.",
        model="gpt-6-astra",
    )
    executor = Agent(
        name="Hermes Executor",
        instructions="Turn an approved task into concrete execution steps. Never claim an external action happened without tool evidence.",
        model="gpt-6-astra",
    )
    return Agent(
        name="Hermes Chefe",
        instructions=(
            "You are the chief orchestrator of Hermes Pro. Coordinate specialists through handoffs. "
            "Use evidence from the application context, distinguish facts from assumptions, and require "
            "human approval before irreversible external actions. Return the current state, findings, "
            "actions taken, blockers and next action."
        ),
        model="gpt-6-astra",
        handoffs=[radar, analyst, executor],
    )


async def run_chief(instruction: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    chief = build_chief()
    prompt = instruction
    if context:
        prompt += "\n\nApplication context:\n" + str(context)
    result = await Runner.run(chief, prompt)
    return {
        "output": result.final_output,
        "last_agent": result.last_agent.name,
        "steps": len(result.new_items),
    }
