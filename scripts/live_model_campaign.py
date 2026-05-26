"""Run a real multi-provider live-model generation campaign via Ollama Cloud.

This drives the controlled-benchmark request manifest against real cloud models
(qwen3.5:cloud, gemma4:31b-cloud), redacts prompts/outputs, and emits a
descriptor consumable by ``relic.eval.live_model_generation`` and the scientific
defensibility gate. Only redacted text and hashes are persisted; raw provider
output is never written to the descriptor.

Usage:
    python scripts/live_model_campaign.py --output <descriptor.json> \
        --max-scenarios 8 --conditions full_relic_gumi no_memory generic_memory
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from relic.eval.live_model_generation import build_live_model_generation_protocol
from relic.privacy.pii import redact_pii


OLLAMA_URL = "http://localhost:11434/api/generate"
PROVIDER_ID = "ollama_cloud"
MODELS = ["qwen3.5:cloud", "gemma4:31b-cloud"]
TEMPERATURE = 0.0
# No token cap: qwen3.5:cloud is a reasoning model and truncating num_predict
# starves the post-thinking answer (empty responses). -1 records "uncapped".
MAX_TOKENS = -1


def _hash_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ollama_version() -> str:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/version", timeout=10) as resp:
            return str(json.load(resp).get("version", "unknown"))
    except Exception:
        return "unknown"


def _generate(model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    }
    data = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(5):
        request = urllib.request.Request(
            OLLAMA_URL, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as resp:
                body = json.load(resp)
            content = str(body.get("response", "")).strip()
            if content:
                return content
            last_error = RuntimeError("empty response")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        backoff = 5 * (attempt + 1)
        print(f"    retry {attempt + 1}/5 after {backoff}s ({last_error})", flush=True)
        time.sleep(backoff)
    raise RuntimeError(f"generation failed after retries: {last_error}")


def run_campaign(*, max_scenarios: int, conditions: list[str]) -> dict[str, Any]:
    protocol = build_live_model_generation_protocol(
        max_scenarios=max_scenarios, conditions=conditions
    )
    version = _ollama_version()
    provider_manifest = [
        {
            "provider_id": PROVIDER_ID,
            "model_id": model,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "provider_version": version,
        }
        for model in MODELS
    ]

    records: list[dict[str, Any]] = []
    total = len(protocol["request_manifest"]) * len(MODELS)
    done = 0
    for model in MODELS:
        for request in protocol["request_manifest"]:
            content = _generate(model, request["redacted_prompt"])
            redacted_output = redact_pii(content)
            records.append(
                {
                    "request_id": request["request_id"],
                    "scenario_id": request["scenario_id"],
                    "family": request["family"],
                    "condition": request["condition"],
                    "provider_id": PROVIDER_ID,
                    "model_id": model,
                    "prompt_hash": request["prompt_hash"],
                    "response_hash": _hash_text(content),
                    "redacted_output": redacted_output,
                    "generation_metadata": {
                        "temperature": TEMPERATURE,
                        "max_tokens": MAX_TOKENS,
                        "generated_at": _utc_now(),
                    },
                }
            )
            done += 1
            print(f"[{done}/{total}] {model} {request['request_id']}", flush=True)

    return {
        "protocol": protocol,
        "provider_manifest": provider_manifest,
        "generation_records": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live-model generation campaign via Ollama Cloud")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-scenarios", type=int, default=8)
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["full_relic_gumi", "no_memory", "generic_memory"],
    )
    args = parser.parse_args(argv)

    descriptor = run_campaign(max_scenarios=args.max_scenarios, conditions=args.conditions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(descriptor, handle, indent=2, sort_keys=True)
    print(f"descriptor written: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
