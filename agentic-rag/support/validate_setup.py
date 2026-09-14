# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""Validate Episode 1 without starting agents or changing application source.

Default: check Python/packages, source configuration, all three containers,
OpenSearch k-NN read/write, and small paid model completions. Capture the actual
SDK parameters in isolated subprocesses before testing provider compatibility.
Use --skip-models for an explicitly INCOMPLETE, infrastructure-only check.
Use --inspect-model-requests to inspect loaded source paths and request fields
without infrastructure checks or paid calls. Inspection also returns INCOMPLETE.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

COMPONENTS = ("2-news-agent", "3-financials-agent", "4-orchestrator-agent")
SCRIPT_DIR = Path(__file__).resolve().parent
TRUE_VALUES = {"1", "true", "yes", "on"}

# This worker executes only configuration loading and model-call construction.
# A capture-only SDK client stops before any network operation or model response.
# Separate interpreters prevent the three projects' `src` packages from colliding.
CAPTURE_WORKER = r'''
import asyncio, dataclasses, hashlib, importlib, json, logging, os, sys
from pathlib import Path
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.getcwd())
component = sys.argv[1]
config_module = 'src.host_agent.config' if component == '4-orchestrator-agent' else 'src.common.config'
settings = importlib.import_module(config_module).load_settings()
config = dataclasses.asdict(settings)
for name in list(config):
    if 'key' in name or 'password' in name:
        value = str(config.pop(name))
        config[name + '_sha256'] = hashlib.sha256(value.encode()).hexdigest()

class Captured(BaseException):
    def __init__(self, kwargs, source):
        self.kwargs = kwargs
        self.source = source
class CaptureClient:
    def __init__(self, **kwargs): self.chat = self; self.completions = self
    async def create(self, **kwargs):
        caller = sys._getframe(1)
        path = Path(caller.f_code.co_filename).resolve()
        source = {'path': str(path), 'line': caller.f_lineno,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        raise Captured(kwargs, source)
    async def close(self): pass
import openai
openai.AsyncOpenAI = CaptureClient
calls = []
async def capture(label, role, coroutine):
    try:
        await coroutine
    except Captured as result:
        params = dict(result.kwargs)
        params.pop('messages', None)
        calls.append({'label': label, 'role': role, 'params': params, 'source': result.source})
    else:
        raise RuntimeError('Expected an SDK call from ' + label)
async def main():
    messages = [{'role': 'user', 'content': 'Setup probe.'}]
    if component == '2-news-agent':
        from src.news_agent.llm import LocalModelGateway
        gateway = LocalModelGateway(settings)
        await capture('planning/verification', 'orch', gateway.orchestrator_completion(messages))
        await capture('synthesis', 'llm', gateway.generator_completion(messages))
    elif component == '3-financials-agent':
        from src.financials_agent.llm import OpenAIModelGateway
        from src.financials_agent.models import FinancialPlan
        gateway = OpenAIModelGateway(settings)
        plan = FinancialPlan()
        await capture('planning', 'orch', gateway.plan('Setup probe.', plan))
        await capture('verification', 'orch', gateway.verify('Setup probe.', 'Probe.', []))
        await capture('synthesis', 'llm', gateway.synthesize('Setup probe.', plan, [], 'setup-probe'))
    else:
        from src.host_agent.llm_client import NemotronOrchestrator
        from src.host_agent.models import RoutingPlan
        gateway = NemotronOrchestrator(settings)
        await capture('planning/completion', 'orch', gateway._structured_call(
            purpose='setup_probe', system_prompt='Setup probe.', user_payload={}, schema=RoutingPlan))
        await capture('synthesis', 'llm', gateway.synthesize_combined(
            company='', user_query='Setup probe.', specialists=[], guidance='', validator=lambda _: None))
asyncio.run(main())
print(json.dumps({'config': config, 'calls': calls}))
'''


class CheckError(RuntimeError):
    """An actionable validation failure."""


@dataclass
class Result:
    name: str
    status: str
    detail: str


def env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def redact(value: object) -> str:
    text = str(value)
    for name, secret in os.environ.items():
        upper = name.upper()
        credential = any(part in upper for part in ("API_KEY", "PASSWORD", "SECRET")) or upper.endswith("_TOKEN") or upper == "TOKEN"
        if credential and len(secret) >= 4:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", text)
    return text[:1800]


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CheckError("External model base URLs must be complete HTTPS URLs.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CheckError("Keep credentials and query parameters out of model base URLs.")
    if parsed.path.rstrip("/").endswith(("/chat/completions", "/responses")):
        raise CheckError("Supply the API base URL, not the complete chat/completions or responses route.")
    return value.rstrip("/")


def provider_key(role: str) -> str:
    name = "OPENAI_API_KEY" if env_true("USE_EXTERNAL_OPENAI") else f"EXTERNAL_{role.upper()}_API_KEY"
    key = os.environ.get(name, "").strip()
    if not key or "<" in key or "YOUR_" in key or key == "not-needed":
        raise CheckError(f"Set a real {name} before running model checks; its value will not be printed.")
    return key


def json_request(url: str, *, method: str = "GET", payload: Any = None,
                 timeout: float = 10.0) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    # Container-local traffic must not go through a host's corporate HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise CheckError("Unexpectedly large JSON response.")
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read(2500).decode(errors="replace")
        raise CheckError(f"HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise CheckError(str(exc)) from None


def wait_json(url: str, ready: Callable[[Any], bool], *, seconds: float,
              timeout: float = 10.0) -> Any:
    deadline = time.monotonic() + seconds
    last_error = "Service is not ready."
    while True:
        try:
            data = json_request(url, timeout=min(timeout, max(1.0, deadline - time.monotonic())))
            if ready(data):
                return data
            last_error = "Endpoint replied, but its reported health is not ready."
        except CheckError as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise CheckError(last_error)
        time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))


def cluster_ready(data: Any) -> bool:
    return isinstance(data, dict) and data.get("status") in {"green", "yellow"} and not data.get("timed_out", False)


def dashboards_ready(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    overall = data.get("status", {}).get("overall", {})
    return overall.get("level") == "available" or overall.get("state") == "green"


def check_dependencies(requirements: Path) -> str:
    from packaging.requirements import Requirement
    missing = []
    for line in requirements.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate():
            continue
        try:
            actual = importlib.metadata.version(req.name)
            if actual not in req.specifier:
                missing.append(f"{req.name} {actual} does not satisfy {req.specifier}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(f"{req.name} is missing")
    if missing:
        raise CheckError("; ".join(missing))
    completed = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True,
                               text=True, timeout=60)
    if completed.returncode:
        raise CheckError(completed.stdout or completed.stderr)
    # Metadata alone does not prove that native extension imports work.
    imports = "import torch,numpy,sentence_transformers,openai,opensearchpy,mcp,a2a; from asgiref.sync import async_to_sync"
    completed = subprocess.run([sys.executable, "-c", imports], capture_output=True,
                               text=True, timeout=180)
    if completed.returncode:
        raise CheckError("Dependency import failed: " + completed.stderr[-1400:])
    return "Requested versions, pip dependency consistency, ML imports, and Flask async support passed."


def capture_component(repo: Path, component: str) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, "-c", CAPTURE_WORKER, component],
                               cwd=repo / component, capture_output=True, text=True, timeout=45)
    if completed.returncode:
        raise CheckError("Source/configuration inspection failed: " + completed.stderr[-1400:])
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise CheckError("Source inspection did not return its expected JSON contract.") from None


def check_vector_roundtrip(base: str) -> str:
    index = "lab-validation-" + uuid.uuid4().hex
    created = False
    try:
        body = {
            "settings": {"index.knn": True, "number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {"properties": {"vector": {
                "type": "knn_vector", "dimension": 3,
                "method": {"name": "hnsw", "engine": "lucene", "space_type": "cosinesimil"}
            }}}
        }
        json_request(f"{base}/{index}", method="PUT", payload=body)
        created = True
        json_request(f"{base}/{index}/_doc/probe?refresh=true", method="PUT",
                     payload={"vector": [1.0, 0.0, 0.0]})
        answer = json_request(f"{base}/{index}/_search", method="POST",
                              payload={"size": 1, "query": {"knn": {"vector": {"vector": [1.0, 0.0, 0.0], "k": 1}}}})
        if not any(hit.get("_id") == "probe" for hit in answer.get("hits", {}).get("hits", [])):
            raise CheckError("The k-NN query did not return its inserted test document.")
    finally:
        if created:
            try:
                json_request(f"{base}/{index}", method="DELETE")
            except CheckError as exc:
                raise CheckError(f"Could not delete temporary index {index}: {exc}") from None
    return "Created, indexed, queried, and deleted a temporary Lucene HNSW cosine index."


def resolve_repo_dir(explicit: Path | None) -> Path:
    """Resolve the source tree after loading any requested environment file."""
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = os.environ.get("LAB_REPO_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    adjacent = SCRIPT_DIR.parent
    if all((adjacent / name / "Makefile").is_file() for name in COMPONENTS):
        return adjacent.resolve()
    return Path.cwd().resolve()


def validate_model_params(base: str, params: dict[str, Any]) -> None:
    """Validate token-limit structure without provider-specific name restrictions.

    Keep the base argument for compatibility with existing callers. The provider
    decides whether the selected model supports the captured parameter name.
    """
    fields = [name for name in ("max_tokens", "max_completion_tokens") if name in params]
    if len(fields) > 1:
        raise CheckError("The application supplied both token-limit fields; send only one.")
    for name in fields:
        value = params[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise CheckError(f"Configured {name} must be a positive integer.")


def request_profile_detail(call: dict[str, Any]) -> str:
    """Show call-site provenance and allowlisted, non-credential parameters."""
    source = call.get("source", {})
    safe_names = ("model", "max_tokens", "max_completion_tokens", "temperature", "top_p", "reasoning_effort")
    params = {name: call["params"][name] for name in safe_names if name in call["params"]}
    return (
        f"{source.get('path', '<unknown>')}:{source.get('line', '?')}; "
        f"sha256={source.get('sha256', '<unknown>')}; "
        f"params={json.dumps(params, sort_keys=True)}"
    )


def model_probe(base: str, key: str, params: dict[str, Any], *, tokens: int,
                full_limits: bool, timeout: float) -> str:
    validate_model_params(base, params)
    from openai import OpenAI
    body = dict(params)
    # The only default alterations are harmless probe messages and a smaller cap.
    # Do not silently rename max_tokens or remove unsupported sampling options.
    for field in ("max_tokens", "max_completion_tokens"):
        if field in body and not full_limits:
            body[field] = min(int(body[field]), tokens)
    body["messages"] = [
        {"role": "system", "content": "This is a connectivity check. Return a brief final answer without explanation."},
        {"role": "user", "content": "Reply with the word READY."},
    ]
    with OpenAI(base_url=base, api_key=key, timeout=timeout, max_retries=0) as client:
        response = client.chat.completions.create(**body)
    choices = response.choices or []
    if not choices:
        raise CheckError("Provider returned no choices.")
    content = choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise CheckError("Provider returned no final text. A reasoning model may need a larger --max-probe-tokens budget.")
    if choices[0].finish_reason == "length":
        raise CheckError("Probe hit its token ceiling; increase --max-probe-tokens and rerun before advancing.")
    return "Received nonempty final text using the source client's request parameters."


def check_embeddings(repo: Path, timeout: float) -> str:
    code = (
        "import sys; sys.path.insert(0,'.'); import numpy as np; "
        "from src.common.config import load_settings; from src.common.embeddings import EmbeddingModel; "
        "m=EmbeddingModel(load_settings()); v=m.encode(['Workshop readiness check.'])[0]; "
        "assert v.ndim==1 and len(v)>0 and np.isfinite(v).all(); "
        "assert abs(float(np.linalg.norm(v))-1.0)<0.01; "
        "print('Embedding dimension:', len(v))"
    )
    process = subprocess.run([sys.executable, "-c", code], cwd=repo / "2-news-agent",
                             capture_output=True, text=True, timeout=timeout)
    if process.returncode:
        raise CheckError("Embedding inference failed: " + process.stderr[-1400:])
    return process.stdout.strip() + "; finite, normalized vector from the repository's embedding wrapper."


class Validator:
    def __init__(self) -> None:
        self.results: list[Result] = []
        self.incomplete = False

    def record(self, name: str, status: str, detail: object) -> None:
        result = Result(name, status, redact(detail))
        self.results.append(result)
        print(f"[{status}] {name}: {result.detail}", flush=True)

    def run(self, name: str, operation: Callable[[], str]) -> bool:
        try:
            self.record(name, "PASS", operation())
            return True
        except Exception as exc:
            self.record(name, "FAIL", f"{type(exc).__name__}: {exc}")
            return False

    def exit_code(self) -> int:
        if any(row.status == "FAIL" for row in self.results):
            return 1
        return 2 if self.incomplete else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-dir", type=Path, help="Source tree to validate. Defaults to LAB_REPO_DIR, then the tree beside this script, then the current directory.")
    parser.add_argument("--inspect-model-requests", action="store_true", help="Only inspect source paths and request fields; no infrastructure checks or paid calls. Returns 2 when inspection succeeds (readiness remains incomplete).")
    parser.add_argument("--env-file", type=Path, help="Native mode: load provider variables without overriding shell exports.")
    parser.add_argument("--native", action="store_true", help="Run in a host Python environment; no lab container expected.")
    parser.add_argument("--skip-models", action="store_true", help="No billable API calls. Returns 2 when otherwise healthy (incomplete).")
    parser.add_argument("--check-embeddings", action="store_true", help="Download/cache the embedding model and run local inference.")
    parser.add_argument("--full-model-limits", action="store_true", help="Send configured token ceilings; potentially expensive. Default caps probes.")
    parser.add_argument("--max-probe-tokens", type=int, default=512)
    parser.add_argument("--wait-seconds", type=float, default=180)
    parser.add_argument("--model-timeout", type=float, default=120)
    parser.add_argument("--embedding-timeout", type=float, default=900)
    parser.add_argument("--json-report", type=Path, help="Write a redacted report with owner-only permissions where supported.")
    args = parser.parse_args()
    if args.max_probe_tokens < 16 or min(args.wait_seconds, args.model_timeout, args.embedding_timeout) <= 0:
        parser.error("Timeouts must be positive and --max-probe-tokens must be at least 16.")
    return args


def finish_validation(validator: Validator, json_report: Path | None,
                      summary: str, *, scope: str = "episode-1") -> int:
    """Print a summary and optionally write the same redacted report contract."""
    code = validator.exit_code()
    print("\n" + summary)
    if json_report:
        report = {"scope": scope, "exit_code": code, "summary": summary,
                  "results": [asdict(result) for result in validator.results]}
        try:
            fd = os.open(json_report, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.fchmod(fd, 0o600)
            except (AttributeError, OSError):
                pass
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2)
                stream.write("\n")
        except OSError as exc:
            print("[FAIL] Could not write report: " + redact(exc), file=sys.stderr)
            return 1
    return code


def main() -> int:
    args = parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        if not args.env_file.is_file():
            print("[FAIL] Environment file not found.", file=sys.stderr)
            return 1
        load_dotenv(args.env_file, override=False)
    repo = resolve_repo_dir(args.repo_dir)
    validator = Validator()
    validator.record("Validator source", "INFO", str(Path(__file__).resolve()))
    validator.record("Repository source", "INFO", str(repo))
    if args.inspect_model_requests:
        validator.incomplete = True
        for component in COMPONENTS:
            try:
                snap = capture_component(repo, component)
                for call in snap["calls"]:
                    name = component + "/" + call["label"]
                    validator.record(name + " request", "INFO", request_profile_detail(call))
                    base = snap["config"][call["role"] + "_url"]
                    try:
                        validate_model_params(base, call["params"])
                        validator.record(name + " inspection", "PASS", "Request captured; no inference call was made.")
                    except CheckError as exc:
                        validator.record(name + " inspection", "FAIL", exc)
            except Exception as exc:
                validator.record(component + " source inspection", "FAIL", exc)
        summary = (
            "INCOMPLETE — source inspection passed; infrastructure and inference were not tested"
            if validator.exit_code() == 2 else "NOT READY — resolve source inspection failures"
        )
        return finish_validation(validator, args.json_report, summary, scope="model-request-inspection")
    validator.record("Scope", "INFO", "Episode 1 readiness only; no specialist, MCP, or Orchestrator service is expected yet.")
    if sys.version_info[:2] == (3, 12):
        validator.record("Python", "PASS", f"{platform.python_version()} on {platform.system()}/{platform.machine()}")
    else:
        validator.record("Python", "FAIL", f"Expected Python 3.12; found {platform.python_version()}.")
    for command in ("git", "make"):
        validator.record(command, "PASS" if shutil.which(command) else "FAIL", "Available." if shutil.which(command) else "Command is missing.")
    validator.run("Dependencies", lambda: check_dependencies(SCRIPT_DIR / "requirements.txt"))
    missing = [part for part in COMPONENTS if not (repo / part / "Makefile").is_file()]
    validator.record("Repository", "FAIL" if missing else "PASS", "Missing components: " + ", ".join(missing) if missing else f"All three component Makefiles exist at {repo}.")
    if not env_true("USE_EXTERNAL_AI"):
        validator.record("External inference", "FAIL", "Set USE_EXTERNAL_AI=true. This episode does not start local LLM servers.")
    else:
        validator.record("External inference", "PASS", "OpenAI mode." if env_true("USE_EXTERNAL_OPENAI") else "Third-party OpenAI-compatible mode.")

    snapshots: dict[str, Any] = {}
    if not missing:
        for component in COMPONENTS:
            try:
                snap = capture_component(repo, component)
                cfg = snap["config"]
                for call in snap["calls"]:
                    validator.record(component + "/" + call["label"] + " request", "INFO", request_profile_detail(call))
                if not all(cfg.get(name) is True for name in ("policy_checks_enabled", "evidence_checks_enabled", "release_checks_enabled")):
                    raise CheckError("Policy, evidence, and release checks must all remain enabled.")
                for role in ("orch", "llm"):
                    actual_url = validate_base_url(cfg[role + "_url"])
                    expected_url = "https://api.openai.com/v1" if env_true("USE_EXTERNAL_OPENAI") else os.environ.get(f"EXTERNAL_{role.upper()}_URL", "")
                    if actual_url != validate_base_url(expected_url):
                        raise CheckError(f"{role} endpoint differs from the selected provider environment.")
                    if not cfg[role + "_model"]:
                        raise CheckError(f"{role} model name is empty.")
                    # Ensure child .env files have not silently chosen a different key.
                    if not args.skip_models:
                        expected = hashlib.sha256(provider_key(role).encode()).hexdigest()
                        if cfg[role + "_api_key_sha256"] != expected:
                            raise CheckError(f"{role} API key differs from the selected provider environment.")
                snapshots[component] = snap
                validator.record(component + " configuration", "PASS",
                                 f"ORCH={cfg['orch_model']} at {cfg['orch_url']}; LLM={cfg['llm_model']} at {cfg['llm_url']}; all governance checks enabled.")
            except Exception as exc:
                validator.record(component + " configuration", "FAIL", exc)

    host = os.environ.get("OPENSEARCH_HOST", "127.0.0.1" if args.native else "opensearch-single")
    port = os.environ.get("OPENSEARCH_PORT", "9200")
    base = f"{'https' if env_true('OPENSEARCH_SSL') else 'http'}://{host}:{port}"
    for component in ("2-news-agent", "3-financials-agent"):
        cfg = snapshots.get(component, {}).get("config", {})
        if cfg and (cfg["opensearch_host"] != host or str(cfg["opensearch_port"]) != port or cfg["opensearch_ssl"] != env_true("OPENSEARCH_SSL")):
            validator.record(component + " OpenSearch target", "FAIL", "Agent configuration does not match the OpenSearch address being validated.")
    def opensearch_check() -> str:
        health = wait_json(base + "/_cluster/health", cluster_ready, seconds=args.wait_seconds)
        info = json_request(base)
        version = info.get("version", {}).get("number")
        if version != "3.5.0":
            raise CheckError(f"Expected OpenSearch 3.5.0, received {version!r}.")
        return f"{base}; version {version}; cluster {health['status']}. Yellow is acceptable for a single-node lab."
    os_ok = validator.run("OpenSearch", opensearch_check)
    if os_ok:
        validator.run("OpenSearch vector read/write", lambda: check_vector_roundtrip(base))
    dashboard_base = os.environ.get("OPENSEARCH_DASHBOARDS_URL", "http://127.0.0.1:5601" if args.native else "http://opensearch-single-dashboards:5601").rstrip("/")
    def dashboard_check() -> str:
        data = wait_json(dashboard_base + "/api/status", dashboards_ready, seconds=args.wait_seconds)
        version = data.get("version", {}).get("number")
        if version != "3.5.0":
            raise CheckError(f"Expected Dashboards 3.5.0, received {version!r}.")
        return "Dashboards 3.5.0 reports available/green, including its OpenSearch connection."
    validator.run("OpenSearch Dashboards", dashboard_check)
    if args.native:
        validator.record("User container", "SKIP", "Not applicable to native Python mode.")
    else:
        def runtime_check() -> str:
            url = os.environ.get("LAB_HEALTH_URL", "http://lab:8088/healthz")
            data = wait_json(url, lambda d: d.get("service") == "agentic-lab" and d.get("status") == "ok" and d.get("repository_ready") is True, seconds=args.wait_seconds)
            if not str(data.get("python", "")).startswith("3.12."):
                raise CheckError("User container readiness endpoint reports an unexpected Python version.")
            return "User container is reachable through network DNS and its workspace is ready."
        validator.run("User container", runtime_check)

    if args.skip_models:
        validator.incomplete = True
        validator.record("External model calls", "SKIP", "Requested --skip-models. Inference has NOT been validated; exit code is 2 unless another check fails.")
    else:
        validator.record("Model probe budget", "INFO", "Configured token ceilings will be sent (potentially high cost)." if args.full_model_limits else f"At most {args.max_probe_tokens} output/reasoning tokens per distinct request profile; paid calls, no retries.")
        profiles: dict[str, dict[str, Any]] = {}
        for component, snap in snapshots.items():
            cfg = snap["config"]
            for call in snap["calls"]:
                role, params = call["role"], call["params"]
                try:
                    key = provider_key(role)
                    url = validate_base_url(cfg[role + "_url"])
                    validate_model_params(url, params)
                    identity = json.dumps([url, hashlib.sha256(key.encode()).hexdigest(), params], sort_keys=True)
                    item = profiles.setdefault(identity, {"url": url, "key": key, "params": params, "labels": []})
                    item["labels"].append(component + "/" + call["label"])
                except Exception as exc:
                    validator.record(component + "/" + call["label"], "FAIL", exc)
        for item in profiles.values():
            name = "Model: " + ", ".join(item["labels"])
            validator.run(name, lambda item=item: model_probe(item["url"], item["key"], item["params"], tokens=args.max_probe_tokens, full_limits=args.full_model_limits, timeout=args.model_timeout))
        if not profiles:
            validator.record("Model request profiles", "FAIL", "No valid application request profiles were available to test.")
        elif not args.full_model_limits:
            validator.record("Full output ceilings", "WARN", "Small probes verify request compatibility, not every provider's configured maximum output budget. See --full-model-limits.")

    if args.check_embeddings and not missing:
        validator.run("Local embedding inference", lambda: check_embeddings(repo, args.embedding_timeout))
    else:
        validator.record("Embedding model download", "SKIP", "Optional. Add --check-embeddings to cache weights and test local inference before Episode 2.")
    validator.record("Later-episode services", "SKIP", "News, Financials, Orchestrator, Tavily MCP, Finnhub MCP, and real corpus ingestion are deliberately not tested in Episode 1.")
    code = validator.exit_code()
    summary = "READY FOR EPISODE 2" if code == 0 else "INCOMPLETE — run the model checks before continuing" if code == 2 else "NOT READY — resolve failed checks and rerun"
    return finish_validation(validator, args.json_report, summary)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nValidation interrupted.", file=sys.stderr)
        raise SystemExit(130)
