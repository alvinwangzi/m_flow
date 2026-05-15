from __future__ import annotations

from m_flow.llm.reasoning import apply_reasoning_options


def test_apply_reasoning_options_disables_qwen_thinking() -> None:
    kwargs = {"model": "qwen3.6-plus", "messages": [], "stream": True}

    apply_reasoning_options(
        request_kwargs=kwargs,
        provider="custom",
        model_name="openai/qwen3.6-plus-2026-04-02",
        reasoning_effort="none",
    )

    assert kwargs["extra_body"]["enable_thinking"] is False
    assert "thinking_budget" not in kwargs["extra_body"]


def test_apply_reasoning_options_enables_qwen_thinking_budget() -> None:
    kwargs = {"model": "qwen3.6-plus", "messages": [], "stream": True}

    apply_reasoning_options(
        request_kwargs=kwargs,
        provider="custom",
        model_name="openai/qwen3.6-plus-2026-04-02",
        reasoning_effort="medium",
    )

    assert kwargs["extra_body"]["enable_thinking"] is True
    assert kwargs["extra_body"]["thinking_budget"] == 2048


def test_apply_reasoning_options_sets_openai_reasoning_effort() -> None:
    kwargs = {"model": "gpt-5-mini", "messages": [], "stream": True}

    apply_reasoning_options(
        request_kwargs=kwargs,
        provider="openai",
        model_name="gpt-5-mini",
        reasoning_effort="low",
    )

    assert kwargs["reasoning_effort"] == "low"
