"""Gemini image generation for Gumi checkins.

Uses gemini-2.5-flash-image via REST with reference images from Visual_Identity/.
"""

from __future__ import annotations

import base64
import hashlib
import json
import requests
from datetime import date
from pathlib import Path
from typing import Optional

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
IMAGE_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

VISUAL_MODES = [
    "close_selfie",
    "mirror_corner_selfie",
    "bed_soft_frame",
    "desk_process_shot",
    "window_or_balcony_portrait",
    "room_detail",
    "neighborhood_ambient",
    "idol_in_progress_frame",
]

VISUAL_MODE_TIME = {
    "morning": ["desk_process_shot", "window_or_balcony_portrait"],
    "afternoon": ["room_detail", "neighborhood_ambient"],
    "evening": ["close_selfie", "mirror_corner_selfie", "bed_soft_frame"],
    "night": ["idol_in_progress_frame", "room_detail"],
}


def load_visual_canon(relic_subject_home: Path) -> dict:
    """Load gumi_visual_canon.json."""
    path = relic_subject_home / "gumi_visual_canon.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_avatar_spec(hermes_home: Path) -> str:
    """Load AVATAR_SPEC.md from profile dir, return content or empty string."""
    path = hermes_home / "AVATAR_SPEC.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def select_visual_mode(time_of_day: str, seed: int) -> str:
    """Select visual mode based on time of day with deterministic fallback."""
    modes = VISUAL_MODE_TIME.get(time_of_day, VISUAL_MODE_TIME["afternoon"])
    index = seed % len(modes)
    return modes[index]


def build_image_prompt(
    avatar_spec: str,
    visual_canon: dict,
    mode: str,
    context_hint: Optional[str] = None,
) -> str:
    """Build fallback image prompt (used when LLM generation is unavailable)."""
    seed_prompt = visual_canon.get("seed_prompt", "")
    mode_desc = mode.replace("_", " ")
    parts = [avatar_spec] if avatar_spec else []
    if seed_prompt:
        parts.append(seed_prompt)
    parts.append(f"Shot style: {mode_desc}. Photorealistic, natural light, candid.")
    if context_hint:
        parts.append(f"Context: {context_hint}")
    return " ".join(parts)


def generate_image_prompt_via_llm(
    avatar_spec: str,
    visual_canon: dict,
    mode: str,
    api_key: str,
    context_hint: Optional[str] = None,
) -> str:
    """Generate a detailed image prompt via Gemini 2.5 Flash."""
    import requests

    palette = ", ".join(visual_canon.get("palette", []))
    motifs = ", ".join(visual_canon.get("motifs", []))
    negative = ", ".join(visual_canon.get("negative_motifs", []))

    meta_prompt = (
        f"Write a concise image generation prompt (max 120 words) for a photorealistic photo "
        f"of this person: {avatar_spec}\n"
        f"Shot style: {mode.replace('_', ' ')}\n"
        f"Visual palette: {palette or 'natural, desaturated'}\n"
        f"Motifs: {motifs or 'everyday life'}\n"
        f"{'Context: ' + context_hint if context_hint else ''}\n"
        f"Avoid: {negative or 'stock photo aesthetics, artificial glow'}. "
        f"Person looks normal and casual, no glamour, no heavy styling. "
        f"Return ONLY the image prompt, no explanations."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    try:
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": meta_prompt}]}]},
            timeout=15,
        )
        if resp.status_code == 200:
            text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if text.strip():
                return text.strip()
    except Exception:
        pass
    # Fallback to template prompt
    return build_image_prompt(avatar_spec, visual_canon, mode, context_hint)


def collect_reference_images(
    relic_subject_home: Path,
    mode: str,
    limit: int = 6,
) -> list[Path]:
    """Collect reference images from Visual_Identity/manifest.json."""
    manifest_path = relic_subject_home / "Visual_Identity" / "manifest.json"
    if not manifest_path.exists():
        return []

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    vi_dir = manifest_path.parent
    images = []
    for entry in manifest.get("entries", []):
        if len(images) >= limit:
            break
        img_path = vi_dir / entry.get("file", "")
        if img_path.exists():
            images.append(img_path)

    return images


def build_api_contents(prompt: str, reference_images: list[Path]) -> list[dict]:
    """Build multimodal contents payload for Gemini API."""
    contents = []

    # Add reference images as inline data
    for img_path in reference_images:
        with open(img_path, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")
        contents.append(
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data,
                }
            }
        )

    # Text prompt
    contents.append({"text": prompt})
    return [{"role": "user", "parts": contents}]


def generate_image(
    prompt: str,
    reference_images: list[Path],
    output_path: Path,
    api_key: str,
    model: str = GEMINI_IMAGE_MODEL,
    timeout: int = 90,
) -> Path:
    """Generate image via Gemini API, save to output_path."""
    contents = build_api_contents(prompt, reference_images)

    url = f"{IMAGE_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {"contents": contents, "generation_config": {"response_modalities": ["IMAGE"]}}

    response = requests.post(url, json=payload, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"Image generation failed: {response.status_code} {response.text[:200]}")

    result = response.json()
    parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    
    image_data = None
    for part in parts:
        # API returns camelCase inlineData; handle both for robustness
        inline = part.get("inlineData") or part.get("inline_data")
        if inline:
            image_data = inline.get("data")
            break

    if not image_data:
        raise RuntimeError("No image in API response")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    media_bytes = base64.standard_b64decode(image_data)
    output_path.write_bytes(media_bytes)

    return output_path


def generate_checkin_image(
    hermes_home: Path,
    relic_subject_home: Path,
    api_key: str,
    time_of_day: str,
    subject_id: str,
    context_hint: Optional[str] = None,
) -> Path:
    """Generate checkin image with deterministic seed."""
    today = date.today()
    seed = int(hashlib.sha256(f"{subject_id}{today}".encode()).hexdigest(), 16) % (2**32)

    mode = select_visual_mode(time_of_day, seed)
    avatar_spec = load_avatar_spec(hermes_home)
    visual_canon = load_visual_canon(relic_subject_home)
    prompt = generate_image_prompt_via_llm(avatar_spec, visual_canon, mode, api_key, context_hint)
    reference_images = collect_reference_images(relic_subject_home, mode)

    tmp_dir = hermes_home / "tmp" / "gumi-images"
    output_path = tmp_dir / f"checkin_{today.isoformat()}_{seed % 10000:04d}.jpg"

    return generate_image(prompt, reference_images, output_path, api_key)
