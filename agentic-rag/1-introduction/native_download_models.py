# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Download the four workshop model artifacts without loading them into memory.

Run with Python from the workshop environment. huggingface_hub is installed as
part of the supplied ML dependencies. No Git LFS checkout is required.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    repo_id: str
    kind: str
    local_name: str
    revision_env: str


MODELS = (
    ModelSpec(
        "mlx-community/Qwen2.5-7B-Instruct-1M-4bit", "mlx",
        "Qwen2.5-7B-Instruct-1M-4bit", "QWEN_MLX_REVISION",
    ),
    ModelSpec(
        "bartowski/Qwen2.5-7B-Instruct-1M-GGUF", "gguf",
        "Qwen2.5-7B-Instruct-1M-Q5_K_M.gguf", "QWEN_GGUF_REVISION",
    ),
    ModelSpec(
        "Mungert/Nemotron-Orchestrator-8B-GGUF", "gguf",
        "Nemotron-Orchestrator-8B-q4_k_m.gguf", "ORCH_GGUF_REVISION",
    ),
    ModelSpec(
        "mlx-community/Orchestrator-8B-4bit", "mlx",
        "Orchestrator-8B-4bit", "ORCH_MLX_REVISION",
    ),
)


def validate_artifact(spec: ModelSpec, models_dir: Path) -> list[Path]:
    """Check expected files, not model quality or compatibility with the backend."""
    path = models_dir / spec.local_name
    if spec.kind == "gguf":
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"Missing or empty GGUF file: {path}")
        with path.open("rb") as stream:
            if stream.read(4) != b"GGUF":
                raise ValueError(f"Not a GGUF file: {path}")
        return [path]

    if not (path / "config.json").is_file():
        raise ValueError(f"Missing MLX config.json: {path}")
    weights = sorted(path.glob("*.safetensors"))
    if not weights or any(p.stat().st_size == 0 for p in weights):
        raise ValueError(f"Missing or empty MLX safetensors weights: {path}")
    files = sorted(p for p in path.rglob("*") if p.is_file() and ".cache" not in p.parts)
    return files


def download_models(models_dir: Path, selection: str = "all") -> Path:
    """Fetch exact GGUF filenames and complete MLX snapshots; record revisions."""
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download

    if selection not in {"all", "gguf", "mlx"}:
        raise ValueError("selection must be all, gguf, or mlx")
    models_dir = models_dir.expanduser().resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = models_dir / "model-manifest.json"
    previous: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous = {item["repo_id"]: item for item in manifest.get("models", [])}

    api = HfApi()
    for spec in MODELS:
        if selection != "all" and spec.kind != selection:
            continue
        requested_revision = os.environ.get(spec.revision_env, "main")
        resolved_revision = api.model_info(spec.repo_id, revision=requested_revision).sha
        if not resolved_revision:
            raise RuntimeError(f"Could not resolve a commit for {spec.repo_id}")
        print(f"Downloading {spec.repo_id} at {resolved_revision}", flush=True)
        if spec.kind == "gguf":
            # Do NOT snapshot the GGUF repository: it contains other quantizations.
            hf_hub_download(
                repo_id=spec.repo_id,
                filename=spec.local_name,
                revision=resolved_revision,
                local_dir=str(models_dir),
            )
        else:
            snapshot_download(
                repo_id=spec.repo_id,
                revision=resolved_revision,
                local_dir=str(models_dir / spec.local_name),
                max_workers=4,
            )
        files = validate_artifact(spec, models_dir)
        previous[spec.repo_id] = {
            "repo_id": spec.repo_id,
            "format": spec.kind,
            "requested_revision": requested_revision,
            "resolved_revision": resolved_revision,
            "local_name": spec.local_name,
            "files": [
                {"path": str(p.relative_to(models_dir)), "bytes": p.stat().st_size}
                for p in files
            ],
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": list(previous.values()),
    }
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    print(f"Model manifest: {manifest_path}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=Path.home() / "models")
    parser.add_argument("--selection", choices=("all", "gguf", "mlx"), default="all")
    args = parser.parse_args()
    try:
        download_models(args.models_dir, args.selection)
    except Exception as exc:
        print(f"Model download failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Check network access, free disk space, model access, and the requested revision.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
