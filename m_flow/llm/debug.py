"""Debug helpers for logging final LLM prompts."""

from __future__ import annotations


def build_llm_prompt_debug_payload(
    *,
    channel: str,
    model: str,
    system_prompt: str,
    user_prompt: str = "",
    messages: list[dict] | None = None,
) -> dict:
    return {
        "channel": channel,
        "model": model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "messages": messages,
        "system_prompt_length": len(system_prompt or ""),
        "user_prompt_length": len(user_prompt or ""),
    }
