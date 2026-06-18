from typing import Any, Dict, Optional

from app.services.llm_client import generate_answer
from app.services.memory_client import (
    fetch_active_facts,
    fetch_beliefs,
    fetch_briefing,
    fetch_digest,
)


def _is_digest_question(question: str) -> bool:
    lowered = question.lower()
    return any(
        token in lowered
        for token in [
            "what changed",
            "changed since",
            "since the last",
            "since last",
            "digest",
            "diff",
        ]
    )


def _format_digest(digest: Dict[str, Any]) -> str:
    lines = []
    if digest.get("changes"):
        lines.append("Changed:")
        for change in digest["changes"]:
            lines.append(
                f"- {change['attribute']}: {change.get('old_value')} → {change.get('new_value')}"
            )
    if digest.get("added"):
        lines.append("Added:")
        for added in digest["added"]:
            lines.append(f"- {added['attribute']}: {added.get('new_value')}")
    if digest.get("removed"):
        lines.append("Removed:")
        for removed in digest["removed"]:
            lines.append(f"- {removed['attribute']}: {removed.get('old_value')}")
    if digest.get("new_conflicts"):
        lines.append("New conflicts:")
        for conflict in digest["new_conflicts"]:
            lines.append(f"- {conflict['description']}")
    if not lines:
        return "No changes since the previous context build."
    return "\n".join(lines)


async def answer_question(
    question: str, entity_id: Optional[str] = None
) -> Dict[str, Any]:
    resolved_id = entity_id or await _resolve_entity_id(question)
    if not resolved_id:
        return {
            "question": question,
            "entity_id": None,
            "answer": (
                "Could not identify the account from the question. "
                "Please provide an explicit entity_id."
            ),
            "context": {},
        }

    if _is_digest_question(question):
        digest = await fetch_digest(resolved_id)
        return {
            "question": question,
            "entity_id": resolved_id,
            "answer": _format_digest(digest),
            "context": {"digest": digest},
        }

    briefing = await fetch_briefing(resolved_id)
    beliefs = await fetch_beliefs(resolved_id)
    context = {
        "briefing": briefing,
        "beliefs": beliefs.get("beliefs", {}),
        "warnings": beliefs.get("warnings", []),
    }
    answer = await generate_answer(question, context)
    return {
        "question": question,
        "entity_id": resolved_id,
        "answer": answer,
        "context": context,
    }


async def _resolve_entity_id(question: str) -> Optional[str]:
    facts = await fetch_active_facts()
    question_lower = question.lower()
    for fact in facts:
        if fact.get("attribute") == "account_name":
            name = str(fact.get("value", "")).lower()
            if name and any(
                len(token) > 2 and token in question_lower for token in name.split()
            ):
                return fact.get("entity_id")
    return None
