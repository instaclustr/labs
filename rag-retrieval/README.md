# RAG Developer Journey — Recipe & Dietary Safety Assistant

A hands-on, six-stage walkthrough of RAG (retrieval-augmented generation)
architectures, each stage fixing a concrete, verified failure of the one
before it. Every stage is runnable end-to-end against a real Instaclustr
OpenSearch cluster and an LLM (Amazon Bedrock, or any OpenAI-compatible
endpoint if you don't have AWS access), on a real (if small and curated)
dataset — not a slide deck.

The running theme is a **"Recipe & Dietary Safety Assistant"**: a system
that answers questions about recipes and their allergen/dietary
information. That theme is deliberately chosen because retrieval mistakes
in it are easy to make *concrete and checkable* — "does this recipe
contain sulfites?" has a factual answer, so every stage's failure mode and
fix can be demonstrated with a real, verified example rather than an
abstract claim. See [`SAFETY_AND_SCOPE.md`](SAFETY_AND_SCOPE.md) for what
that does and does not mean about this being production dietary-safety
advice (it is not).

## Why this journey, and why should you care
If you've shipped a RAG system to production, you've probably run into one
of these without realizing it had a name:
- **Wrong, but confident.** You ask "does this recipe have peanuts?" and
  the system finds a *different* recipe that sounds almost the same, and
  answers as if it were the right one — because it matched on wording, not
  on facts.
- **The fix needs its own babysitter.** You add exact keyword matching (so
  "peanuts" only matches recipes that actually say "peanuts") — but now
  you're running a second, separate service just to spot which words
  matter, and it has to stay running alongside everything else.
- **Combining two guesses isn't a guarantee.** You blend keyword matching
  and similarity search into one score, hoping to get the best of both —
  but averaging two guesses still isn't a promise. A recipe that says
  "contains peanuts" can still outscore one that doesn't, and slip through.
- **You didn't know some data was safety-critical.** You move older or
  rarely-used data to slower, cheaper storage to save cost — without
  checking whether any of it was allergen or safety information, which can
  now arrive late or get missed.
- **"Why did it say that?" — and you have nothing.** The system gives a
  wrong or risky answer, someone asks what it looked at and why, and
  there's no record of what was searched, what was found, or why it picked
  that answer.
Each stage in this repo reproduces exactly one of these on a real dataset,
against a real OpenSearch cluster and a real LLM — not as a slide claim,
but as something you run and watch break, then run again and watch get
fixed. By the end, you have a working mental model *and* working code for
the difference between "a RAG demo" and "a RAG system you can actually
trust and defend."

**Who this is for:** developers and engineers building, reviewing, or
inheriting a RAG system who want to recognize these failure modes by name
before they show up in production, not after.


## The journey, stage by stage

Each stage has its own `README.md` with a specific **teaching goal**, a
`Run it` section, and a `validate.py` smoke test with verified sample
output. All six stages run on the same "Recipe & Dietary Safety Assistant"
dataset, each one isolating and fixing a single retrieval failure of the
stage before it.

| Stage | What it adds | Fixes |
|---|---|---|
| [1 — Baseline Vector RAG](01_baseline_vector_rag_recipes/README.md) | Plain kNN vector search | — |
| [2 — Baseline BM25 RAG](02_baseline_bm25_rag_recipes/README.md) | BM25 + NER entity tagging | Vector search confusing semantically-similar-but-factually-different questions |
| [3 — Hybrid RAG (Native OpenSearch)](03_hybrid_rag_native_opensearch/README.md) | Server-side BM25+kNN fusion via a search pipeline, one index | Needing a whole separate NER microservice just to disambiguate |
| [4 — Hybrid RAG (External NER + Grounding/Refine)](04_hybrid_rag_external_ner_rerank/README.md) | Two-phase ground (BM25, hard filters) → refine (vector rerank) | Similarity *scores* can't guarantee a hard exclusion like "no sulfites" |
| [5 — Governance-Driven Hot/LT Tiering](05_governance_hot_lt_tiering/README.md) | Safety-driven hot/archive tiering, escalation, audit log, citation-tagging | Treating all data as equally reachable regardless of safety criticality; no record of *why* a query reached what it reached |
| [6 — Harden for Production](06_operationalize_production/README.md) | Governance-signal monitoring, audit-log retention, policy change control | Nobody watching the audit trail Stage 5 introduced; unbounded audit growth; undocumented threshold drift |

![Overview diagram](./overview_diagram.png)

Full rationale, `common/` design, and index-naming scheme:
[`ARCHITECTURE.md`](ARCHITECTURE.md). Production hardening checklist
(automated + manual): [`OPERATIONAL_CHECKLIST.md`](OPERATIONAL_CHECKLIST.md).
Setup problems: [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## Repo layout

```
common/                              Shared config, LLM (Bedrock/OpenAI)/OpenSearch/NER clients, embeddings, logging
01_baseline_vector_rag_recipes/      Stage 1
02_baseline_bm25_rag_recipes/        Stage 2
03_hybrid_rag_native_opensearch/     Stage 3
04_hybrid_rag_external_ner_rerank/   Stage 4
05_governance_hot_lt_tiering/        Stage 5
06_operationalize_production/        Stage 6
requirements.txt                     Single shared dependency set for every stage
.env.example                         Every stage's configuration, in one place
```

Each numbered stage directory follows the same internal shape:
`README.md`, `ingest.py`, `query.py` (plus `ner_service.py` for stages that
need NER), `validate.py`, and a `recipes/` folder with the curated sample
data. Stage 6 is the exception — see its README for why.

## Quick start

**1. Accounts you'll need** (all free-tier friendly):
- An [Instaclustr](https://www.instaclustr.com/) OpenSearch cluster (every
  stage shares one cluster; each stage just uses different index names).
- An LLM provider — pick one:
  - AWS account with **Bedrock model access enabled** for at least one
    Anthropic Claude model (AWS console → Bedrock → Model access — this is
    a separate opt-in step per model, not automatic), **or**
  - An OpenAI (or OpenAI-compatible) API key — no AWS account needed. Set
    `LLM_PROVIDER=openai` in `.env` (see step 3).
- (Optional) A [HuggingFace](https://huggingface.co/) token, only needed if
  you want to regenerate `recipes_sample.json` from the source dataset
  yourself — the curated sample is already committed, so this isn't
  required to run any stage.

**2. Set up the environment:**

```bash
git clone <this repo>
cd rag-retrieval
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # needed by every stage's ner_service.py
```

**3. Configure:**

```bash
cp .env.example .env
# then edit .env: OPENSEARCH_HOST/USER/PASSWORD, and either --
#   Bedrock (default): AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY, AWS_REGION, and
#   BEDROCK_MODEL_ID (exact ID from Bedrock's Model access page), or
#   OpenAI: set LLM_PROVIDER=openai, then OPENAI_API_KEY and OPENAI_MODEL.
```

**4. Pick a stage and follow its README**, starting with
[Stage 1](01_baseline_vector_rag_recipes/README.md) if you want the full
progression, or jump straight to whichever failure mode you're curious
about. Every stage's `README.md` has its own `Run it` and `Validate`
sections with real, verified sample output.

## What's shared vs. what's per-stage

Every stage imports the same `common/` package (OpenSearch client
factory + query builders, the LLM `generate()` that dispatches to Bedrock
or OpenAI, the local NER client, embeddings, config loading) and reads
from the same `.env` file — see
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the full breakdown. What changes
stage-to-stage is which index(es) it reads/writes and how it builds its
query, not the underlying plumbing. That's intentional: the point of this
repo is to isolate *one architectural change at a time* so its effect is
easy to see and verify.
