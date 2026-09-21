# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Verify Episode 1 prerequisites without loading another copy of either model."""
from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import sys
from urllib.request import urlopen

from packaging.requirements import Requirement
from packaging.version import Version

from download_models import MODELS, validate_artifact


def get_json(url: str, timeout: float = 10) -> dict:
    with urlopen(url, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object from {url}")
    return payload


def check_dependencies(requirements_file: Path) -> tuple[list[str], int]:
    failures = []
    applicable = 0
    for line in requirements_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate():
            continue
        applicable += 1
        try:
            installed = metadata.version(req.name)
            if Version(installed) not in req.specifier:
                failures.append(f"{req.name}: installed {installed}; required {req.specifier}")
        except metadata.PackageNotFoundError:
            failures.append(f"Missing dependency: {req.name}")
    return failures, applicable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=Path.home() / "models")
    parser.add_argument("--services", action="store_true", help="Also check model-service health on ports 8001 and 8002.")
    args = parser.parse_args()
    failures = []

    if sys.version_info[:2] == (3, 12):
        print(f"PASS Python {platform.python_version()}")
    else:
        failures.append(f"Expected Python 3.12; found {platform.python_version()}")
    print(f"INFO Platform: {platform.system()} {platform.machine()}")

    dependency_failures, count = check_dependencies(Path(__file__).parent / "requirements.txt")
    failures.extend(dependency_failures)
    if not dependency_failures:
        print(f"PASS {count} applicable requirement entries")

    for spec in MODELS:
        try:
            validate_artifact(spec, args.models_dir.expanduser())
            print(f"PASS Model files: {spec.local_name}")
        except (OSError, ValueError) as exc:
            failures.append(str(exc))

    host = os.environ.get("OPENSEARCH_HOST", "127.0.0.1")
    port = os.environ.get("OPENSEARCH_PORT", "9200")
    search_url = f"http://{host}:{port}"
    try:
        info = get_json(search_url)
        version = info.get("version", {}).get("number")
        if version != "3.5.0":
            failures.append(f"Expected OpenSearch 3.5.0; found {version!r}")
        health = get_json(search_url + "/_cluster/health")
        status = health.get("status")
        if status not in {"green", "yellow"}:
            failures.append(f"OpenSearch is not ready: status={status!r}")
        elif version == "3.5.0":
            print(f"PASS OpenSearch {version} at {search_url} ({status})")
    except Exception as exc:
        failures.append(f"Cannot verify OpenSearch at {search_url}: {exc}")

    if args.services:
        for port in (8001, 8002):
            try:
                health = get_json(f"http://127.0.0.1:{port}/health")
                if health.get("status") != "ok" or health.get("server", {}).get("port") != port:
                    failures.append(f"Unexpected health response on port {port}: {health}")
                else:
                    print(f"PASS Model service {port}: {health.get('model')} ({health.get('runtime')})")
            except Exception as exc:
                failures.append(f"Model service {port} is not ready: {exc}")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        print("Resolve the failed checks before continuing.", file=sys.stderr)
        return 1
    print("Environment checks passed. A chat-completion request is still needed to test generation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
