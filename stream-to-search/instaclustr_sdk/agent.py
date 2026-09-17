"""AI agent module — analyzes and explains anomalies found by the detection algorithm.

A z-score flag is a statistical signal, not a verdict. This module uses an LLM (Claude by
default, or any provider Pydantic AI supports) to judge whether a flagged point is a genuine
anomaly worth attention or a benign artifact, grounded in the RAG knowledge base (domain
context + past findings, see instaclustr_sdk/rag.py).

Two entry points, both returning a typed `Verdict`:

    import instaclustr_sdk.agent as agent
    agent.setup()             # Claude Opus 5, unless INSTACLUSTR_SDK_AGENT_MODEL names another model

    # single model request, augmented with retrieved RAG context
    verdict = agent.explain_anomaly(anomaly, remember=True)

    # full agentic investigation — the model pulls metric stats and searches memory via tools
    verdict = agent.investigate_anomaly(anomaly)

Requires the `[ai]` extra (`pip install "instaclustr-sdk[ai]"`). The model loop, tool calling, and
structured output belong to Pydantic AI; this module only supplies the instructions, the
`Verdict` schema, and two tools that reach back into instaclustr_sdk.search and instaclustr_sdk.rag. `setup()`
accepts any Pydantic AI model and returns the underlying `Agent` for anything beyond these
entry points.
"""
from __future__ import annotations

import os
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.capabilities import RaiseContentFilterError, Thinking
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset

from . import detection, rag, search

DEFAULT_MODEL = "anthropic:claude-opus-5"
"""The model `setup()` uses when it gets none and `MODEL_ENV_VAR` is unset."""

MODEL_ENV_VAR = "INSTACLUSTR_SDK_AGENT_MODEL"
"""Names the model when `setup()` gets none, e.g. "openai:gpt-5.2" (any Pydantic AI model name)."""

# Pydantic AI's Anthropic default is 4096, which adaptive thinking can use up before the
# answer; 16000 stays within non-streaming request timeouts.
DEFAULT_MODEL_SETTINGS: ModelSettings = {"max_tokens": 16000}
"""Settings every run starts from; `setup(model_settings=...)` is merged over them."""

INSTRUCTIONS = f"""You are an anomaly-analysis assistant for a real-time streaming metrics platform.

Anomalies are flagged by a simple z-score rule: a point whose value is more than \
{detection.DEFAULT_THRESHOLD:g} standard deviations from the trailing per-(entity, metric) mean. \
That rule is a statistical trigger, not proof of a real problem — a flag can be a genuine \
incident, or a benign artifact such as a sensor glitch/disconnect, an expected spike, \
seasonality, or a cold start with little history.

Judge each flagged point using the domain context and past findings you are given (or can \
retrieve). Be concise and decisive."""
"""The agent's instructions, shared by `explain_anomaly` and `investigate_anomaly`."""


class Verdict(BaseModel):
    """The agent's judgment of one flagged point."""

    verdict: Literal["genuine", "benign", "uncertain"] = Field(
        description="Whether the flagged point is a real problem worth acting on."
    )
    cause: str = Field(description="The most likely cause of the flagged value.")
    action: str = Field(description="The recommended next action.")

    def __str__(self) -> str:
        return f"Verdict: {self.verdict}\nCause: {self.cause}\nAction: {self.action}"


# --- Tools: the only places the agent reaches back into instaclustr_sdk ---------------------------
# Thin wrappers rather than the raw functions: metric_stats' `window` is interpolated into
# SQL and must not be model-controlled. Both are sequential because search and rag each hold
# one ClickHouse client, and ClickHouse runs one query at a time per session.

tools = FunctionToolset()
"""The tools `investigate_anomaly` offers the model: `get_metric_stats` and `search_knowledge`."""


@tools.tool_plain(sequential=True)
def get_metric_stats(entity: str, metric: str) -> Dict[str, object]:
    """Get recent statistics (count, mean, stddev, min, max, latest value) for a metric.

    Covers the trailing hour of events. Use this to see whether a flagged value is an
    isolated spike or part of a sustained shift.

    Args:
        entity: The entity name, e.g. "sensor-1".
        metric: The metric name, e.g. "temperature".
    """
    return search.metric_stats(entity, metric)


@tools.tool_plain(sequential=True)
def search_knowledge(query: str) -> List[Dict[str, str]]:
    """Search domain knowledge and past anomaly findings for relevant context.

    Use this to recall what is / isn't a real anomaly for this kind of signal, and how
    similar cases were judged before.

    Args:
        query: A natural-language description of what you're looking for.
    """
    return [{"kind": d.kind, "text": d.text} for d in rag.retrieve(query, k=5)]


# --- Lifecycle and entry points ---------------------------------------------------------

_agent: Optional[Agent] = None


def setup(
    model: Union[str, Model, None] = None,
    model_settings: Optional[ModelSettings] = None,
) -> Agent:
    """Build the agent. `model` is any Pydantic AI model name or `Model` instance.

    Without one, INSTACLUSTR_SDK_AGENT_MODEL names the model, else Claude Opus 5. A provider other
    than Anthropic needs its Pydantic AI extra (e.g. `pip install "instaclustr-sdk[ai,openai]"`)
    and its own credentials; the default reads ANTHROPIC_API_KEY. For custom clients or platforms
    (Bedrock, Vertex, Foundry), pass a `Model` built on your own client. `model_settings` are
    merged over the defaults, e.g. `{"max_tokens": 32000}`.
    """
    global _agent
    _agent = Agent(
        model or os.environ.get(MODEL_ENV_VAR) or DEFAULT_MODEL,
        output_type=Verdict,
        instructions=INSTRUCTIONS,
        model_settings={**DEFAULT_MODEL_SETTINGS, **(model_settings or {})},
        capabilities=[Thinking(effort="high"), RaiseContentFilterError()],
    )
    return _agent


def _require() -> Agent:
    if _agent is None:
        raise RuntimeError("instaclustr_sdk.agent.setup(...) must be called first")
    return _agent


def _describe(anomaly) -> str:
    return f"""Flagged point:
  entity:    {anomaly.entity}
  metric:    {anomaly.metric}
  value:     {anomaly.value}
  z-score:   {anomaly.zscore}
  timestamp: {anomaly.ts}"""


def explain_anomaly(anomaly, k: int = 5, remember: bool = False) -> Verdict:
    """Judge one anomaly with a single model request, grounded in retrieved RAG context.

    If `remember` is set, the verdict is written back to the knowledge base as a 'finding'
    so future analyses can learn from it.
    """
    agent = _require()

    context_docs = []
    try:
        context_docs = rag.retrieve(
            query=f"{anomaly.entity} {anomaly.metric} anomaly value {anomaly.value}",
            k=k,
            entity=anomaly.entity,
        )
    except Exception:
        pass  # RAG is optional context; proceed without it if unavailable
    context = "\n".join(f"- [{d.kind}] {d.text}" for d in context_docs) or "(no prior context found)"

    prompt = f"""{_describe(anomaly)}

Domain context and past findings (retrieved):
{context}

Analyze this flagged point."""
    verdict = agent.run_sync(prompt).output

    if remember:
        try:
            rag.add_finding(
                anomaly,
                verdict=verdict.verdict,
                explanation=f"{verdict.cause} Recommended action: {verdict.action}",
            )
        except Exception:
            pass
    return verdict


def investigate_anomaly(anomaly) -> Verdict:
    """Full agentic analysis: the model decides which tools to call, then delivers a verdict.

    Requires instaclustr_sdk.search.setup() and instaclustr_sdk.rag.setup() so the tools have their backends.
    """
    prompt = f"""{_describe(anomaly)}

Investigate using the available tools, then give your verdict."""
    return _require().run_sync(prompt, toolsets=[tools]).output
