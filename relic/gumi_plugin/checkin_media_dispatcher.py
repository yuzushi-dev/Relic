"""Checkin media dispatcher — routes LLM output to appropriate media generators.

Handles text, voice, image, and music delivery after gate decision.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from relic.gumi_plugin.media_state import record_media_delivery
from relic.gumi_plugin.image_gen import generate_checkin_image
from relic.gumi_plugin.tts import synthesize_checkin_audio
from relic.gumi_plugin.lyria import LyriaGenerator


def parse_gate_output(llm_output: str) -> dict:
    """Parse gate output to extract media type and content.

    Returns dict with keys:
        tipo: "text"|"voice"|"image"|"music"
        testo: full content (for text/voice/music)
        caption: extracted caption line (for image)
        image_prompt: extracted image_prompt line (for image)
    """
    lines = llm_output.strip().split("\n")
    media_type = "text"
    content_lines = []
    caption = ""
    image_prompt = ""

    for line in lines:
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("tipo:"):
            media_type = stripped.split(":", 1)[1].strip().lower()
        elif low.startswith("ora:"):
            pass
        elif low.startswith("caption:"):
            caption = stripped.split(":", 1)[1].strip()
        elif low.startswith("image_prompt:"):
            image_prompt = stripped.split(":", 1)[1].strip()
        else:
            content_lines.append(stripped)

    testo = "\n".join(l for l in content_lines if l).strip()

    return {
        "tipo": media_type,
        "testo": testo,
        "caption": caption,
        "image_prompt": image_prompt,
    }


def _get_api_key() -> Optional[str]:
    """Get GEMINI_API_KEY from .env file in Hermes home."""
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        env_path = Path(hermes_home) / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key.strip() == "GEMINI_API_KEY":
                        return val.strip()
    return os.environ.get("GEMINI_API_KEY")


def dispatch(
    llm_output: str,
    hermes_home: Path,
    relic_subject_home: Path,
    subject_id: str,
    dry_run: bool = False,
) -> dict:
    """Dispatch media based on gate output.
    
    Args:
        llm_output: Raw LLM output from checkin_message
        hermes_home: Path to Hermes profile home
        relic_subject_home: Path to subject's relic home
        subject_id: Subject ID
        dry_run: If True, simulate without API calls
    
    Returns:
        {"tipo": str, "success": bool, "output": str}
    """
    parsed = parse_gate_output(llm_output)
    tipo = parsed["tipo"]
    testo = parsed["testo"]
    
    api_key = _get_api_key()

    if tipo == "text":
        print(testo)
        return {"tipo": "text", "success": True, "output": testo}

    elif tipo == "voice":
        if dry_run:
            print("[DRY-RUN] Voice synthesis skipped")
            return {"tipo": "voice", "success": True, "dry_run": True}
        
        if not api_key:
            print(f"[WARN] No GEMINI_API_KEY, skipping voice")
            return {"tipo": "voice", "success": False, "reason": "no_api_key"}
        
        audio_path = synthesize_checkin_audio(
            text=testo,
            hermes_home=hermes_home,
            relic_subject_home=relic_subject_home,
            api_key=api_key,
        )
        record_media_delivery(hermes_home, "voice")
        print(f"MEDIA:{audio_path}")
        return {"tipo": "voice", "success": True, "audio_path": str(audio_path)}

    elif tipo == "image":
        if dry_run:
            print("[DRY-RUN] Image generation skipped")
            return {"tipo": "image", "success": True, "dry_run": True}

        if not api_key:
            print("[WARN] No GEMINI_API_KEY, skipping image")
            return {"tipo": "image", "success": False, "reason": "no_api_key"}

        caption = parsed["caption"] or testo
        image_prompt = parsed["image_prompt"]

        if image_prompt:
            # Gumi wrote the image prompt — use it directly
            from relic.gumi_plugin.image_gen import generate_image, collect_reference_images
            from datetime import date
            import hashlib
            ref_images = collect_reference_images(relic_subject_home, "close_selfie")
            today = date.today()
            seed = int(hashlib.sha256(f"{subject_id}{today}".encode()).hexdigest(), 16) % 10000
            tmp_dir = hermes_home / "tmp" / "gumi-images"
            output_path = tmp_dir / f"checkin_{today.isoformat()}_{seed:04d}.jpg"
            image_path = generate_image(image_prompt, ref_images, output_path, api_key)
        else:
            # Fallback: no image_prompt from Gumi, generate via checkin pipeline
            from datetime import datetime as _dt
            hour = _dt.now().hour
            time_of_day = "morning" if 6 <= hour < 12 else "afternoon" if 12 <= hour < 18 else "evening" if 18 <= hour < 22 else "night"
            image_path = generate_checkin_image(
                hermes_home=hermes_home,
                relic_subject_home=relic_subject_home,
                api_key=api_key,
                time_of_day=time_of_day,
                subject_id=subject_id,
                context_hint=testo,
            )

        record_media_delivery(hermes_home, "image")
        print(f"{caption}\nMEDIA:{image_path}")
        return {"tipo": "image", "success": True, "image_path": str(image_path), "caption": caption}

    elif tipo == "music":
        if dry_run:
            print("[DRY-RUN] Music generation skipped")
            return {"tipo": "music", "success": True, "dry_run": True}

        if not api_key:
            print("[WARN] No GEMINI_API_KEY, skipping music")
            return {"tipo": "music", "success": False, "reason": "no_api_key"}

        # testo IS the Lyria prompt written by Gumi
        lyria_prompt = testo
        if not lyria_prompt:
            return {"tipo": "music", "success": False, "reason": "empty_lyria_prompt"}

        generator = LyriaGenerator(
            hermes_home=hermes_home,
            relic_subject_home=relic_subject_home,
            api_key=api_key,
        )
        result = generator.generate_and_deliver(
            target=subject_id,
            lyria_prompt=lyria_prompt,
            dry_run=False,
        )

        if not result.get("success"):
            print("[WARN] Music generation failed")  # lgtm[py/clear-text-logging-sensitive-data]
            return {"tipo": "music", "success": False, "reason": result.get("reason")}

        record_media_delivery(hermes_home, "music")
        caption = result.get("caption", "")
        media_file = result.get("audio_path", "")
        print(f"{caption}\nMEDIA:{media_file}")
        return {"tipo": "music", "success": True, "audio_path": media_file, "caption": caption}

    else:
        print(testo)
        return {"tipo": "text", "success": True, "output": testo}


def main():
    """CLI entry point for checkin media dispatcher."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Checkin media dispatcher")
    parser.add_argument("--llm-output", required=True, help="LLM output from checkin_message")
    parser.add_argument("--hermes-home", type=Path, help="Hermes profile home path")
    parser.add_argument("--subject-home", type=Path, help="Relic subject home path")
    parser.add_argument("--subject-id", required=True, help="Subject ID")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without API calls")
    
    args = parser.parse_args()
    
    # Get paths from environment if not provided
    hermes_home = args.hermes_home or Path(os.environ.get(
        "HERMES_HOME",
        f"{os.environ.get('HOME')}/.hermes/profiles/gumi-{args.subject_id}"
    ))
    relic_subject_home = args.subject_home or Path(os.environ.get(
        "RELIC_SUBJECT_HOME",
        f"{os.environ.get('HOME')}/.relic/subjects/{args.subject_id}"
    ))
    
    dispatch(
        llm_output=args.llm_output,
        hermes_home=hermes_home,
        relic_subject_home=relic_subject_home,
        subject_id=args.subject_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
