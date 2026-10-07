# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Governed Financials Agent exposed through A2A and backed by RAG plus MCP."""

from .financials_agent import FinancialAgent, FinancialsAgent

__all__ = ["FinancialsAgent", "FinancialAgent"]
