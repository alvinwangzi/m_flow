"""Provider-aware reasoning parameter mapping for LLM calls."""

from __future__ import annotations


def normalize_reasoning_effort(reasoning_effort: str | None) -> str:
    effort = (reasoning_effort or "medium").lower()
    if effort not in {"none", "low", "medium", "high"}:
        return "medium"
    return effort


def apply_reasoning_options(
    *,
    request_kwargs: dict,
    provider: str,
    model_name: str,
    reasoning_effort: str | None,
) -> None:
    """Map unified reasoning settings to provider/model-specific request params."""
    effort = normalize_reasoning_effort(reasoning_effort)
    model_lower = (model_name or "").lower()
    provider_lower = (provider or "").lower()

    # Qwen via DashScope OpenAI-compatible API
    if "qwen" in model_lower:
        extra_body = dict(request_kwargs.get("extra_body") or {})
        if effort == "none":
            extra_body["enable_thinking"] = False
            extra_body.pop("thinking_budget", None)
        else:
            extra_body["enable_thinking"] = True
            budget_map = {
                "low": 512,
                "medium": 2048,
                "high": 8192,
            }
            extra_body["thinking_budget"] = budget_map[effort]
        request_kwargs["extra_body"] = extra_body
        return

    # OpenAI reasoning-capable models
    if provider_lower == "openai" or "gpt-5" in model_lower or model_lower.startswith(("o1", "o3", "o4")):
        request_kwargs["reasoning_effort"] = effort


def get_reasoning_debug_payload(
    *,
    provider: str,
    model_name: str,
    reasoning_effort: str | None,
    request_kwargs: dict,
) -> dict:
    """Return a compact debug payload showing the effective reasoning parameters."""
    effort = normalize_reasoning_effort(reasoning_effort)
    return {
        "provider": provider,
        "model": model_name,
        "configured_effort": effort,
        "reasoning_effort": request_kwargs.get("reasoning_effort"),
        "extra_body": request_kwargs.get("extra_body"),
    }
