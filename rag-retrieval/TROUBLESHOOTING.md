# Troubleshooting

Common setup and runtime issues across stages, and how to fix them. If
something isn't covered here, check the specific stage's `README.md` first
— several document stage-specific "what to look for" output that can help
distinguish a real bug from expected behavior (e.g. Stage 5's escalation).

## Setup

### `RuntimeError: Missing configuration in .env`

Raised by `common/config.py`'s `require_configured()`, which every stage
calls before connecting to anything. The message lists exactly which
values are missing/still placeholders (`OPENSEARCH_HOST`,
`OPENSEARCH_USER`/`PASSWORD`, `BEDROCK_MODEL_ID`). Fix: `cp .env.example
.env` if you haven't already, then fill in real values — a stale copy of
`.env.example` with the placeholder host
(`your-cluster-host.instaclustr.com`) triggers this same error.

### `OSError: [E050] Can't find model 'en_core_web_sm'`

`ner_service.py` (Stages 2, 4, 5) needs spaCy's small English model,
which isn't installed by `pip install -r requirements.txt` alone:

```bash
python -m spacy download en_core_web_sm
```

### `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`

Two common causes, both handled automatically by `common/__init__.py` on
import — if you still see this, something's preventing that self-heal:

1. **Python installed via the official python.org `.pkg` installer**
   doesn't wire itself up to any certificate trust store, so *any* HTTPS
   call fails, network restrictions aside.
2. **A corporate TLS-inspecting proxy** (Zscaler, Netskope, etc.) re-signs
   HTTPS traffic with a certificate the OS keychain trusts but a plain
   `certifi` bundle does not.

`common/__init__.py` merges macOS System-keychain roots into a local
combined bundle (`.cache/merged-ca-bundle.pem`) and points
`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`/`AWS_CA_BUNDLE` at it automatically.
This is macOS-specific (`sys.platform == "darwin"`) and best-effort — on
Linux/Windows, or if this still doesn't resolve it, fall back to
installing your proxy's root CA into `certifi`'s bundle manually, or set
`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` yourself before running any stage.

### `AccessDeniedException` calling Bedrock

Bedrock model access is an explicit **per-model opt-in** in the AWS
console (Bedrock → Model access), separate from having Bedrock IAM
permissions at all. Check that the exact model in `BEDROCK_MODEL_ID` shows
as "Access granted" there — not just that your IAM user/role has
`bedrock:InvokeModel`.

### `ValidationException: The provided model identifier is invalid`

`BEDROCK_MODEL_ID` must be the exact model ID string from Bedrock's Model
access page (e.g.
`anthropic.claude-3-5-sonnet-20241022-v2:0`), and it must be available in
the region set by `AWS_REGION` — Bedrock model availability varies by
region.

## Runtime

### Query results look wrong / entity matching isn't kicking in

Check whether `ner_service.py` is actually running (Stages 2, 4, 5
all depend on it). `common/ner_client.py`'s `NERClient` deliberately
**swallows** connection failures into an empty entity list rather than
raising, so a downed NER service degrades silently to plain full-text
matching instead of erroring — you'll get an answer, just a worse one,
with no error message telling you why. Stage 6's `monitor.py` exists
specifically to catch this in production; in dev, just check the
terminal you started it in.

### `Address already in use` starting `ner_service.py`

Default port is 8000 (`PORT` env var to override). If Stage 2's
`ner_service.py` is already running, Stage 4/5's `query.py` can reuse it
directly — no need to start a second copy (see each stage's README, which
says "same one Stage 2 uses").

### OpenSearch connection suddenly fails after previously working

If `OPENSEARCH_HOST` hasn't changed but connections still fail, verify the
value in your *current* `.env` against the Instaclustr console — a
cluster's load-balancer hostname can change (e.g. after a resize/restore),
and a stale hostname produces a generic connection-timeout error that
looks like a network problem, not a config problem.

### `TransportError` / warnings when running Stage 6's `monitor.py` or `validate.py` mentioning `_plugins/_ism`

Some managed OpenSearch tiers restrict or disable the ISM (Index State
Management) plugin. `ensure_audit_retention_policy()` is written to
degrade gracefully — it returns `False` and logs a warning rather than
raising, and Stage 6's `validate.py` reports `[SKIP]` rather than failing
in this case. Treat it as a manual-review item (see
`OPERATIONAL_CHECKLIST.md` section A), not a bug.

### Stage 5/6's `recipes-audit-log` queries return nothing

`audit_log_governance_stats()`/Stage 5's audit write are scoped to a
`timestamp` range (default: trailing 24h in `monitor.py`). If you're
checking older data, pass a larger `--lookback-hours` to `monitor.py`, or
query the index directly without a time filter.

### Results differ from a stage's documented "verified output"

Every stage's README's "What to look for" section includes real,
previously-verified output (exact scores, exact escalation reasons). Small
score differences are expected — they depend on the exact state of your
index (re-running `ingest.py` doesn't guarantee identical document scoring
if you've ingested extra/fewer documents, or if your OpenSearch cluster
version differs). The *qualitative* result (which recipe wins, whether
escalation triggers) should still match; if it doesn't, check that
`ingest.py` completed successfully and the expected recipe count landed in
the index before assuming a real bug.
