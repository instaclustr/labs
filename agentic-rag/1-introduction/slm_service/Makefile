# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Run from this directory. The active Python environment must contain requirements.txt.
.DEFAULT_GOAL := service
PYTHON ?= python
LLM_SERVER_HOST ?= 0.0.0.0
LLM_SERVER_PORT ?= 8001
LLM_SERVER_MODEL ?= Qwen/Qwen2.5-7B-Instruct-1M
# Workshop override: the supplied Python code defaults to 65,536 tokens.
LLAMA_CTX ?= 8192
export LLM_SERVER_HOST LLM_SERVER_PORT LLM_SERVER_MODEL LLAMA_CTX

.PHONY: service slm-service
service:
	$(PYTHON) slm_service.py

slm-service: service
