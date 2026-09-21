# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0s

# Run from this directory. The active Python environment must contain requirements.txt.
.DEFAULT_GOAL := service
PYTHON ?= python
LLM_SERVER_HOST ?= 0.0.0.0
LLM_SERVER_PORT ?= 8002
LLM_SERVER_MODEL ?= nvidia/Nemotron-Orchestrator-8B
# Workshop override: the supplied Python code defaults to 65,536 tokens.
LLAMA_CTX ?= 8192
export LLM_SERVER_HOST LLM_SERVER_PORT LLM_SERVER_MODEL LLAMA_CTX

.PHONY: service orch-service
service:
	$(PYTHON) orch_service.py

orch-service: service
