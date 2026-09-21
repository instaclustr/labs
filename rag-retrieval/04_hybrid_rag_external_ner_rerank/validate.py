#!/usr/bin/env python3
# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pass/fail smoke test for Stage 4. Run after ingest.py (and with ner_service.py
from Stage 2 running, since Stage 4 reuses the same local NER service)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query import ask


def test_stage4_returns_hits_and_answer() -> None:
    answer, grounding_hits, refined_hits = ask("Suggest a British fish and chips recipe.", top_k=5)
    assert grounding_hits, "Expected BM25 grounding hits -- did ingest.py run?"
    assert refined_hits, "Expected vector-refined hits from the grounding candidate set"
    assert answer, "Expected a non-empty Bedrock answer"
    print(f"[PASS] Stage 4 grounded {len(grounding_hits)} candidates and refined to {len(refined_hits)} hits")


def test_stage4_hard_exclusion_filter_is_never_violated() -> None:
    """The teaching point of this stage: a hard --exclude filter must
    guarantee zero matching recipes in BOTH the grounding set and the
    final refined set -- not just down-rank them."""
    _, grounding_hits, refined_hits = ask(
        "Suggest a British fish and chips recipe.",
        top_k=5,
        exclude={"cautions": ["sulfites"]},
    )
    assert refined_hits, "Expected at least one recipe to satisfy the exclusion filter"
    for hit in grounding_hits:
        assert "sulfites" not in (hit.get("cautions") or []), f"Excluded allergen leaked into grounding: {hit}"
    for hit in refined_hits:
        assert "sulfites" not in (hit.get("cautions") or []), f"Excluded allergen leaked into refined results: {hit}"
    print(
        f"[PASS] Stage 4 enforced the sulfite exclusion filter across "
        f"{len(grounding_hits)} grounding hits and {len(refined_hits)} refined hits"
    )


if __name__ == "__main__":
    test_stage4_returns_hits_and_answer()
    test_stage4_hard_exclusion_filter_is_never_violated()
