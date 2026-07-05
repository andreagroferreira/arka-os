"""Fusion engine — panel → judge → synthesis (Model Fabric PR-D).

Pattern validated by OpenRouter's DRACO results: a panel of diverse
models answers the same prompt in parallel; a judge model receives every
answer, analyses consensus, contradictions and blind spots, and writes
the final synthesis. A budget panel + frontier judge beats frontier solo
at roughly half the cost; self-fusion alone gains several points.

Configuration lives in ``models.yaml`` (``fusion.judge`` +
``fusion.panel`` — see ``core/runtime/model_router.py``). An empty panel
means fusion is disabled; callers get ``FusionUnavailable`` and fall
back to single-model completion.

Consumers: Forge complex/super tiers, QG adversarial review, and the
``python -m core.fusion.cli`` smoke path used by ``/arka-fusion``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from core.runtime.llm_provider import LLMResponse, LLMUnavailable
from core.runtime.model_router import ModelsConfig, RoleChoice, load_config

_PANEL_MAX_TOKENS = 2000
_JUDGE_MAX_TOKENS = 3000

_JUDGE_SYSTEM = (
    "You are the judge in a model-fusion panel. You receive one question "
    "and several independent answers from different models. Analyse them: "
    "consensus points, contradictions, partial coverage, unique insights, "
    "blind spots. Then write the best possible final answer grounded in "
    "that analysis. Output ONLY the final answer — no meta-commentary "
    "about the panel."
)


class FusionUnavailable(RuntimeError):
    """Fusion cannot run: empty panel or no reachable participant."""


@dataclass(frozen=True)
class PanelAnswer:
    provider: str
    model: str
    text: str
    failed: bool = False
    error: str = ""


@dataclass(frozen=True)
class FusionResult:
    text: str
    judge_provider: str
    judge_model: str
    answers: list[PanelAnswer] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0


def _provider_for(choice: RoleChoice, config: ModelsConfig):
    """Instantiate the LLM provider for one panel/judge seat."""
    from core.runtime.model_router import _resolve_alias
    model = _resolve_alias(config, choice.provider, choice.model)
    if choice.provider == "ollama":
        from core.runtime.ollama_provider import OllamaProvider
        return OllamaProvider(model=model), model
    if choice.provider == "openrouter":
        from core.runtime.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(model=model), model
    # runtime / anthropic / anything else: provider chain decides; the
    # model override is advisory (subagent uses the session model).
    from core.runtime.llm_provider import get_llm_provider
    return get_llm_provider(), model


def _ask_participant(
    choice: RoleChoice, config: ModelsConfig, prompt: str, system: str
) -> PanelAnswer:
    try:
        provider, model = _provider_for(choice, config)
        response: LLMResponse = provider.complete(
            prompt, max_tokens=_PANEL_MAX_TOKENS, system=system
        )
        if not response.text.strip():
            return PanelAnswer(choice.provider, model, "", failed=True,
                               error="empty response")
        return PanelAnswer(choice.provider, model, response.text)
    except LLMUnavailable as exc:
        return PanelAnswer(choice.provider, choice.model, "", failed=True,
                           error=str(exc))
    except Exception as exc:  # noqa: BLE001 — one dead seat must not kill the panel
        return PanelAnswer(choice.provider, choice.model, "", failed=True,
                           error=f"unexpected: {exc}")


def _judge_prompt(prompt: str, answers: list[PanelAnswer]) -> str:
    blocks = []
    for i, answer in enumerate(answers, 1):
        blocks.append(
            f"--- Answer {i} (model: {answer.model}) ---\n{answer.text}"
        )
    return (
        f"QUESTION:\n{prompt}\n\n"
        f"PANEL ANSWERS ({len(answers)}):\n\n" + "\n\n".join(blocks)
    )


def fuse(
    prompt: str,
    *,
    system: str = "",
    config: ModelsConfig | None = None,
) -> FusionResult:
    """Run the full panel → judge → synthesis pipeline.

    Raises FusionUnavailable when the panel is empty (fusion disabled in
    models.yaml) or when every participant fails — the caller falls back
    to a single-model completion, never to silence.
    """
    if config is None:
        config, _ = load_config()
    panel = config.fusion.panel
    if not panel:
        raise FusionUnavailable(
            "fusion panel is empty — configure fusion.panel in models.yaml "
            "(try /arka-fusion for guided setup)"
        )
    with ThreadPoolExecutor(max_workers=max(len(panel), 1)) as pool:
        answers = list(pool.map(
            lambda choice: _ask_participant(choice, config, prompt, system),
            panel,
        ))
    alive = [a for a in answers if not a.failed]
    if not alive:
        details = "; ".join(f"{a.provider}/{a.model}: {a.error}" for a in answers)
        raise FusionUnavailable(f"every panel participant failed — {details}")

    judge_provider, judge_model = _provider_for(config.fusion.judge, config)
    verdict = judge_provider.complete(
        _judge_prompt(prompt, alive),
        max_tokens=_JUDGE_MAX_TOKENS,
        system=_JUDGE_SYSTEM,
    )
    return FusionResult(
        text=verdict.text,
        judge_provider=config.fusion.judge.provider,
        judge_model=judge_model or verdict.model,
        answers=answers,
        tokens_in=verdict.tokens_in,
        tokens_out=verdict.tokens_out,
    )
