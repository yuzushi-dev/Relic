"""Tests for image_gen.py — Gemini image generation."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.image_gen import (
    VISUAL_MODES,
    build_image_prompt,
    collect_reference_images,
    select_visual_mode,
)


def test_select_visual_mode_returns_valid(tmp_path: Path) -> None:
    for tod in ("morning", "afternoon", "evening", "night"):
        mode = select_visual_mode(tod, seed=42)
        assert mode in VISUAL_MODES


def test_select_visual_mode_deterministic() -> None:
    m1 = select_visual_mode("morning", seed=7)
    m2 = select_visual_mode("morning", seed=7)
    assert m1 == m2


def test_build_image_prompt_nonempty() -> None:
    avatar_spec = "Una persona normale, capelli scuri, abiti casual"
    visual_canon = {"style": "quiet naturalism", "palette": [], "motifs": [], "negative_motifs": []}
    prompt = build_image_prompt(avatar_spec, visual_canon, "close_selfie")
    assert isinstance(prompt, str)
    assert len(prompt) > 10
    assert "close_selfie" in prompt or "selfie" in prompt.lower() or avatar_spec[:10] in prompt


def test_collect_reference_images_empty_dir(tmp_path: Path) -> None:
    relic_home = tmp_path / "relic"
    relic_home.mkdir()
    images = collect_reference_images(relic_home, "close_selfie")
    assert isinstance(images, list)
    assert images == []


def test_collect_reference_images_with_manifest(tmp_path: Path) -> None:
    relic_home = tmp_path / "relic"
    vi_dir = relic_home / "Visual_Identity"
    vi_dir.mkdir(parents=True)
    img = vi_dir / "anchor.jpg"
    img.write_bytes(b"JPEG")
    manifest = {"entries": [{"file": "anchor.jpg", "use_for_identity_anchor": True, "strength": 1.0}]}
    (vi_dir / "manifest.json").write_text(json.dumps(manifest))
    images = collect_reference_images(relic_home, "close_selfie")
    assert img in images


def test_generate_image_writes_file(tmp_path: Path) -> None:
    from relic.gumi_plugin.image_gen import generate_image

    fake_jpeg = base64.b64encode(b"FAKEJPEG").decode()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"inline_data": {"data": fake_jpeg, "mimeType": "image/jpeg"}}]
            }
        }]
    }

    output = tmp_path / "out.jpg"
    with patch("requests.post", return_value=mock_response):
        result = generate_image("test prompt", [], output, "fake-api-key")
    assert result == output
    assert output.exists()


def test_generate_image_raises_on_error(tmp_path: Path) -> None:
    from relic.gumi_plugin.image_gen import generate_image

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    output = tmp_path / "out.jpg"
    with patch("requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError):
            generate_image("test prompt", [], output, "fake-api-key")
