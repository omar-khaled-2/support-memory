import json
from typing import Any, Dict

from openai import AsyncOpenAI

from app.config import get_settings


async def generate_answer(question: str, context: Dict[str, Any]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to generate answers")

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
