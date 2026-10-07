# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: server agent test check audit

server: agent
agent:
	python -m src.host_agent

test:
	pytest -q

check:
	python -m compileall -q client.py src tests
	pytest -q

audit:
	python -m src.host_agent.audit
