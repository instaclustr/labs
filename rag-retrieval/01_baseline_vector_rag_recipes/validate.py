#!/usr/bin/env python3
# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pass/fail smoke test for Stage 1. Run after ingest.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query import ask


def test_stage1_returns_hits_and_answer() -> None:
    answer, hits = ask(
        "Does the thegratefulgirlcooks.com Fish and Chips recipe contain sulfites?", top_k=5, num_candidates=25
    )
    assert answer, "Expected a non-empty answer from Bedrock"
    assert len(hits) > 0, "Expected at least one retrieved recipe -- did ingest.py run?"
    print(f"[PASS] Stage 1 returned {len(hits)} hits and a {len(answer)}-char answer")


if __name__ == "__main__":
    test_stage1_returns_hits_and_answer()
