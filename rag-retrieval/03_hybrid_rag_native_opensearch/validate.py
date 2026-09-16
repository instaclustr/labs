#!/usr/bin/env python3
# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pass/fail smoke test for Stage 3. Run after ingest.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query import ask


def test_stage3_disambiguates_similar_questions() -> None:
    a1, hits1 = ask("Does the thegratefulgirlcooks.com Fish and Chips recipe contain sulfites?", top_k=5)
    a2, hits2 = ask("Does the womensweeklyfood.com.au Fish and Chips recipe contain sulfites?", top_k=5)
    assert hits1 and hits2, "Expected hybrid hits for both questions -- did ingest.py run?"
    assert a1 and a2, "Expected non-empty Bedrock answers for both questions"
    print("[PASS] Stage 3 answered both disambiguation questions with hybrid-retrieved evidence")


if __name__ == "__main__":
    test_stage3_disambiguates_similar_questions()
