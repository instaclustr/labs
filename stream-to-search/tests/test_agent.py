"""Offline unit tests for instaclustr_sdk.agent — no API key, Kafka, or ClickHouse needed.

Pydantic AI's TestModel stands in for the model: it calls every tool a run offers, then
returns schema-valid structured output. The request-shape tests run the real Anthropic and
OpenAI clients against a mocked HTTP transport. Needs the [ai] extra (and [dev] for OpenAI);
skipped without it.
"""
import json

import pytest

pytest.importorskip("pydantic_ai")

import httpx2
from anthropic import AsyncAnthropic
from pydantic_ai import capture_run_messages, models
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider

import instaclustr_sdk.agent as agent
from instaclustr_sdk import Anomaly, rag, search

ANOMALY = Anomaly(
    event_id="e1", entity="sensor-1", metric="temperature",
    value=95.0, ts="2026-09-11 12:00:00.000", zscore=148.2,
)
DOMAIN_RULE = "Single spikes above 90C are disconnects."


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Block real model requests and start every test with no agent configured."""
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    monkeypatch.setattr(agent, "_agent", None)


@pytest.fixture
def backends(monkeypatch):
    """Replace the ClickHouse-backed calls the agent makes, recording what it asked for."""
    calls = {"stats": [], "retrieve": [], "findings": []}

    def metric_stats(entity, metric):
        calls["stats"].append((entity, metric))
        return {"entity": entity, "metric": metric, "count": 600, "mean": 20.1, "stddev": 0.5}

    def retrieve(query, k=5, kind=None, entity=None):
        calls["retrieve"].append(query)
        return [rag.Doc(text=DOMAIN_RULE, kind="domain", entity="sensor-1",
                        metric="temperature", distance=0.1)]

    def add_finding(anomaly, verdict, explanation):
        calls["findings"].append((anomaly.event_id, verdict))

    monkeypatch.setattr(search, "metric_stats", metric_stats)
    monkeypatch.setattr(rag, "retrieve", retrieve)
    monkeypatch.setattr(rag, "add_finding", add_finding)
    return calls


def test_calls_before_setup_raise():
    with pytest.raises(RuntimeError, match="setup"):
        agent.explain_anomaly(ANOMALY)


def test_setup_takes_the_model_from_the_environment(monkeypatch):
    monkeypatch.setenv(agent.MODEL_ENV_VAR, "test")  # Pydantic AI's name for TestModel

    agent.setup()

    assert isinstance(agent.explain_anomaly(ANOMALY), agent.Verdict)


def test_an_explicit_model_beats_the_environment(monkeypatch):
    monkeypatch.setenv(agent.MODEL_ENV_VAR, "no-such-provider:no-such-model")

    agent.setup(TestModel())

    assert isinstance(agent.explain_anomaly(ANOMALY), agent.Verdict)


def test_investigate_uses_both_tools_and_returns_verdict(backends):
    agent.setup(TestModel())

    verdict = agent.investigate_anomaly(ANOMALY)

    assert isinstance(verdict, agent.Verdict)
    assert backends["stats"] and backends["retrieve"]


def test_explain_is_one_request_without_tools_and_remembers_verdict(backends):
    model = TestModel()
    agent.setup(model)

    with capture_run_messages() as messages:
        verdict = agent.explain_anomaly(ANOMALY, remember=True)

    assert model.last_model_request_parameters.function_tools == []
    assert [m.kind for m in messages].count("response") == 1
    prompt = next(p.content for p in messages[0].parts if p.part_kind == "user-prompt")
    assert DOMAIN_RULE in prompt
    assert backends["stats"] == []
    assert backends["findings"] == [("e1", verdict.verdict)]


def test_default_settings_reach_the_anthropic_request(monkeypatch, backends):
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)  # the transport below is mocked
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json={
            "id": f"msg_{len(bodies)}", "type": "message", "role": "assistant",
            "model": "claude-opus-5", "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [{"type": "tool_use", "id": f"toolu_{len(bodies)}", "name": "final_result",
                         "input": {"verdict": "benign", "cause": "disconnect", "action": "ignore"}}],
        })

    client = AsyncAnthropic(api_key="test", max_retries=0,
                            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    agent.setup(AnthropicModel("claude-opus-5", provider=AnthropicProvider(anthropic_client=client)))

    assert agent.explain_anomaly(ANOMALY).verdict == "benign"
    assert agent.investigate_anomaly(ANOMALY).verdict == "benign"

    explain, investigate = bodies
    assert explain["model"] == "claude-opus-5"
    assert explain["max_tokens"] == 16000
    assert explain["thinking"] == {"type": "adaptive"}
    assert explain["output_config"]["effort"] == "high"
    assert [t["name"] for t in explain["tools"]] == ["final_result"]
    assert {t["name"] for t in investigate["tools"]} == {
        "get_metric_stats", "search_knowledge", "final_result",
    }


VERDICT_ARGS = json.dumps({"verdict": "benign", "cause": "disconnect", "action": "ignore"})


def _openai_responses_reply(n):
    return {"id": f"resp_{n}", "object": "response", "created_at": 0, "model": "gpt-5.2",
            "status": "completed", "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
            "output": [{"type": "function_call", "id": f"fc_{n}", "call_id": f"call_{n}",
                        "name": "final_result", "arguments": VERDICT_ARGS, "status": "completed"}],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                      "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 0}}}


def _openai_chat_reply(n):
    return {"id": f"chat_{n}", "object": "chat.completion", "created": 0, "model": "gpt-4.1",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None, "tool_calls": [{
                    "id": f"call_{n}", "type": "function",
                    "function": {"name": "final_result", "arguments": VERDICT_ARGS}}]}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


@pytest.mark.parametrize(
    "api, model_name, reasoning",
    [
        ("responses", "gpt-5.2", {"effort": "high"}),  # a reasoning model gets the effort
        ("chat", "gpt-4.1", None),  # a non-reasoning model gets no reasoning parameter
    ],
)
def test_default_settings_reach_openai_requests(monkeypatch, backends, api, model_name, reasoning):
    pytest.importorskip("openai")
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)  # the transport below is mocked
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        reply = _openai_responses_reply if api == "responses" else _openai_chat_reply
        return httpx2.Response(200, json=reply(len(bodies)))

    client = AsyncOpenAI(api_key="test", max_retries=0,
                         http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    model_class = OpenAIResponsesModel if api == "responses" else OpenAIChatModel
    agent.setup(model_class(model_name, provider=OpenAIProvider(openai_client=client)))

    assert agent.explain_anomaly(ANOMALY).verdict == "benign"
    assert agent.investigate_anomaly(ANOMALY).verdict == "benign"

    explain, investigate = bodies
    assert explain.get("reasoning") == reasoning
    assert "reasoning_effort" not in explain
    assert explain.get("max_output_tokens", explain.get("max_completion_tokens")) == 16000

    def tool_names(body):
        return {t.get("name") or t["function"]["name"] for t in body["tools"]}

    assert tool_names(explain) == {"final_result"}
    assert tool_names(investigate) == {"get_metric_stats", "search_knowledge", "final_result"}
