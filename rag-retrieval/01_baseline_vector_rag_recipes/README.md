# Stage 1 — Baseline Vector RAG (Recipes)

The first stage in the journey: plain vector (kNN) search over the "Recipe &
Dietary Safety Assistant" dataset, before any fix is applied.

**Wrong, but confident — with real stakes.** Same failure as Stage 1, now
on the actual allergen data: a wrong-but-confident answer here isn't just
an annoying demo bug, it's the exact mistake this whole journey exists to
prevent.

**Teaching goal:** vector search retrieves by *semantic similarity*, not by
*factual correctness*. Two similarly-worded questions can have completely
different correct answers, and pure vector retrieval has no way to know
that -- it just returns "similar-sounding" recipes.

## Dataset

A curated sample of 260 recipes (`recipes/recipes_sample.json`) pulled from
[`datahiveai/recipes-with-nutrition`](https://huggingface.co/datasets/datahiveai/recipes-with-nutrition)
on HuggingFace -- already included, no download step needed.

The sample deliberately includes a **real, naturally-occurring ambiguous pair**
found in the source dataset: two completely different recipes that both happen
to be named **"Fish and Chips"**:

| | Source | Cautions |
|---|---|---|
| Recipe A | thegratefulgirlcooks.com | *(none listed)* |
| Recipe B | womensweeklyfood.com.au | **Sulfites** |

Only Recipe B (which uses beer in its batter) carries a sulfites caution.
This pair was chosen after empirically verifying it actually breaks vector
retrieval, not just because the names match: with the `all-MiniLM-L6-v2`
embedding model, the question about Recipe A scores *higher* against
Recipe B's embedding (0.62) than against its own (0.49) -- a genuine
ranking flip, not just a close call. A secondary, thinner-margin pair
("Chicken Cordon Bleu" -- Skinnytaste vs. sargento.com, soy vs. no-soy) is
also included in the sample for further exploration.

## Run it

```bash
source ../.venv/bin/activate   # from repo root: source .venv/bin/activate
cd 01_baseline_vector_rag_recipes

python ingest.py
python query.py --question "Does the thegratefulgirlcooks.com Fish and Chips recipe contain sulfites?"
python query.py --question "Does the womensweeklyfood.com.au Fish and Chips recipe contain sulfites?"
```

## What to look for (verified output)

Asking about **thegratefulgirlcooks.com**'s recipe (the correct answer is
"no sulfites"): vector search's top-5 hits don't include that recipe at
all -- only womensweeklyfood.com.au's same-named recipe shows up. Because
Stage 1's system prompt instructs the model to say "I don't know" when the
context doesn't support an answer, you'll see the assistant correctly
decline rather than hallucinate -- but the *retrieval* still silently failed
to find the one document that actually answers the question. With a looser
system prompt (or a model that ignores it), this is exactly the shape of
failure that produces a confidently wrong safety answer instead.

Asking about **womensweeklyfood.com.au**'s recipe works fine, since that
recipe legitimately ranks near the top of the corpus regardless.

This failure mode is directly tied to dietary safety here -- a dropped or
wrong retrieval isn't just an inaccurate trivia fact, it's the kind of gap
that matters for someone with a sulfite sensitivity. Stage 2's BM25 +
entity retrieval is designed to close this exact gap (verified: it
correctly answers both questions).

## Validate

```bash
python validate.py
```
