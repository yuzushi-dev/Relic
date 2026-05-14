#!/usr/bin/env python3
"""Verify Lyria model availability for a given API key."""

import argparse
import requests


def verify_lyria_models(api_key: str) -> dict[str, bool]:
    """Check which Lyria models are available."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Error: API returned {response.status_code}")
            return {}

        data = response.json()
        available = {m["name"].split("/")[-1] for m in data.get("models", [])}

        models = {
            "lyria-3-clip-preview": "Lyria 3 (primary)",
            "lyria-realtime-exp": "Lyria Realtime (fallback)",
        }

        print("\nLyria Model Availability:")
        print("-" * 40)
        for model_id, name in models.items():
            status = "✓ available" if model_id in available else "✗ unavailable"
            print(f"  {name}: {status}")

        return {
            "lyria-3-clip-preview": model_id in available,
            "lyria-realtime-exp": model_id in available,
        }
    except Exception as e:
        print(f"Error: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Verify Lyria model availability")
    parser.add_argument("--key", required=True, help="GEMINI_API_KEY")
    args = parser.parse_args()

    results = verify_lyria_models(args.key)
    if not any(results.values()):
        print("\nWarning: No Lyria models available!")
        print("Music generation will fail until models are enabled.")


if __name__ == "__main__":
    main()
