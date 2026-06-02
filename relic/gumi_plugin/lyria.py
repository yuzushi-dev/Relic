"""Lyria 3 music generation for Gumi.

Generates mood-based audio clips using Lyria models via google-genai SDK.
Includes caption generation via Gemini.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

LYRIA_MODEL_PRIMARY = "lyria-3-clip-preview"
LYRIA_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

LYRIA_STATE_PATH = "state/lyria_music_state.json"
MUSIC_COOLDOWN_DAYS = 7
MUSIC_COOLDOWN_FLOOR_DAYS = 14


class LyriaGenerator:
    def __init__(self, hermes_home: Path, relic_subject_home: Path, api_key: str):
        self.hermes_home = hermes_home
        self.relic_subject_home = relic_subject_home
        self.api_key = api_key
        self._state: Optional[dict] = None

    def _state_path(self) -> Path:
        return self.hermes_home / LYRIA_STATE_PATH

    def _load_state(self) -> dict:
        if self._state is not None:
            return self._state
        path = self._state_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._state = {}
        else:
            self._state = {}
        return self._state

    def _save_state(self, state: dict) -> None:
        self._state = state
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def _read_memory(self) -> str:
        """Read Gumi memory from Hermes MEMORY.md."""
        memory_path = self.hermes_home / "MEMORY.md"
        if memory_path.exists():
            return memory_path.read_text(encoding="utf-8")[:2000]  # limit context
        return ""

    def _read_background(self) -> dict:
        """Read background profile."""
        bg_path = self.relic_subject_home / "gumi_background_profile.json"
        if bg_path.exists():
            with open(bg_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def can_generate(self, *, force: bool = False) -> tuple[bool, str]:
        """Check if music generation is allowed (cooldown elapsed)."""
        state = self._load_state()
        last_gen = state.get("last_generation")
        
        if not last_gen:
            return True, "Never generated before"

        try:
            last_ts = datetime.fromisoformat(last_gen.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return True, "Invalid timestamp"

        now = datetime.now(timezone.utc)
        elapsed_days = (now - last_ts).total_seconds() / 86400

        # Floor rule: always allow if > 14 days
        if elapsed_days >= MUSIC_COOLDOWN_FLOOR_DAYS:
            return True, f"Floor rule: {elapsed_days:.1f} days elapsed"

        # Normal cooldown: 7 days
        if force or elapsed_days >= MUSIC_COOLDOWN_DAYS:
            return True, f"Cooldown satisfied: {elapsed_days:.1f} days"

        return False, f"Cooldown active: {elapsed_days:.1f}/{MUSIC_COOLDOWN_DAYS} days"

    def _build_lyric_prompt(self, mood_hint: Optional[str] = None) -> str:
        """Build Lyria prompt with Italian vocal lyrics using Gemini 2.5 Flash."""
        import requests
        memory = self._read_memory()
        bg = self._read_background()

        persona = bg.get("persona_summary", "Una persona normale, calda e riflessiva")
        _emb = bg.get("embodiment") if isinstance(bg.get("embodiment"), dict) else {}
        gender = str(
            _emb.get("gender_expression")
            or bg.get("gender_expression")
            or bg.get("gender")
            or ""
        ).lower()
        if "masc" in gender or gender in {"male", "man"}:
            singer_profile = "Male baritone, warm and calm timbre"
        elif "femin" in gender or gender in {"female", "woman"}:
            singer_profile = "Female mezzo-soprano, warm and intimate timbre"
        else:
            singer_profile = "Androgynous mid-range voice, warm and intimate timbre"
        context_snippet = memory[:300] if memory else ""
        mood = mood_hint or "malinconico e sognante"

        meta_prompt = (
            f"Write a prompt for Lyria 3 (AI music generator) to create a 30-second clip "
            f"with sung vocals in English. The clip is sent by an AI companion named Gumi "
            f"to a friend. Persona: {persona}. Mood: {mood}. "
            f"{'Recent context: ' + context_snippet if context_snippet else ''}\n\n"
            f"The prompt must include:\n"
            f"- Singer profile: {singer_profile}\n"
            f"- Musical style (e.g. acoustic pop, indie folk, singer-songwriter)\n"
            f"- [Verse] with 2 lines in English (max 10 words per line, natural, not cheesy)\n"
            f"- [Chorus] with 2 lines in English (short, memorable)\n"
            f"Return ONLY the Lyria prompt text, no explanations."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": meta_prompt}]}]},
            timeout=20,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Lyrics prompt generation failed: {resp.status_code}")

        result = resp.json()
        text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return text.strip()

    def generate_and_deliver(
        self,
        target: str,
        lyria_prompt: Optional[str] = None,
        seed_hint: Optional[str] = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> dict:
        """Generate and deliver music clip with vocals."""
        can_gen, reason = self.can_generate(force=force)
        if not can_gen:
            return {"success": False, "reason": reason}

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "caption": "Preview: brano vocale generato da Lyria",
                "audio_path": None,
                "reason": reason,
            }

        # Use agent-provided prompt; fallback to LLM-generated if missing
        lyric_prompt = lyria_prompt or self._build_lyric_prompt(seed_hint)

        # Generate via Lyria REST API: returns audio + lyrics text
        try:
            audio_path, returned_lyrics = self._call_lyria(lyric_prompt)
        except Exception as e:
            return {"success": False, "reason": f"Lyria generation failed: {e}"}

        # Caption: use returned lyrics if available, else short summary
        caption = returned_lyrics.strip()[:120] if returned_lyrics else "🎵"

        # Update state
        state = self._load_state()
        state["last_generation"] = datetime.now(timezone.utc).isoformat()
        self._save_state(state)

        return {
            "success": True,
            "caption": caption,
            "audio_path": str(audio_path),
            "lyrics_prompt": lyric_prompt,
        }

    def _call_lyria(self, prompt: str, model: str = LYRIA_MODEL_PRIMARY) -> tuple[Path, str]:
        """Call Lyria 3 REST API. Returns (audio_path, lyrics_text)."""
        import base64
        import requests

        url = f"{LYRIA_API_BASE}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO", "TEXT"],
            },
        }

        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Lyria API error {resp.status_code}: {resp.text[:300]}")

        result = resp.json()
        parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])

        audio_b64 = None
        lyrics_text = ""
        for part in parts:
            if "inlineData" in part:
                audio_b64 = part["inlineData"].get("data")
            elif "inline_data" in part:
                audio_b64 = part["inline_data"].get("data")
            elif "text" in part:
                lyrics_text += part["text"]

        if not audio_b64:
            raise RuntimeError("No audio in Lyria response")

        tmp_dir = self.hermes_home / "tmp" / "gumi-music"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = tmp_dir / f"music_{timestamp}.mp3"

        media_bytes = base64.standard_b64decode(audio_b64)
        output_path.write_bytes(media_bytes)

        return output_path, lyrics_text


def verify_lyria_models(api_key: str) -> dict[str, bool]:
    """Verify which Lyria models are available."""
    import requests
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {LYRIA_MODEL_PRIMARY: False}

        data = response.json()
        available = {m["name"].split("/")[-1] for m in data.get("models", [])}

        return {LYRIA_MODEL_PRIMARY: LYRIA_MODEL_PRIMARY in available}
    except Exception:
        return {LYRIA_MODEL_PRIMARY: False}
