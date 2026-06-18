import json
from typing import Any, Dict

from openai import AsyncOpenAI

from app.config import get_settings


async def generate_answer(question: str, context: Dict[str, Any]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback_answer(context)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a support assistant. Answer concisely using only the "
                "provided customer context."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Context:\n{json.dumps(context, indent=2, default=str)}\n\n"
                "Answer:"
            ),
        },
    ]
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=settings.openai_temperature,
    )
    return response.choices[0].message.content.strip()


def _fallback_answer(context: Dict[str, Any]) -> str:
    briefing = context.get("briefing", {})
    beliefs = context.get("beliefs", {})
    warnings = list(context.get("warnings", []))
    warnings.extend(briefing.get("warnings", []))

    lines = []
    if briefing.get("account_name"):
        lines.append(f"Account: {briefing['account_name']}")
    if briefing.get("active_plan"):
        lines.append(f"Plan: {briefing['active_plan']}")
    if briefing.get("region"):
        lines.append(f"Region: {briefing['region']}")
    if briefing.get("tier"):
        lines.append(f"Tier: {briefing['tier']}")
    if beliefs:
        lines.append("Key facts: " + ", ".join(f"{k}={v}" for k, v in beliefs.items()))
    if warnings:
        lines.append("Warnings: " + "; ".join(warnings))

    return "\n".join(lines) if lines else "No relevant context found."
