"""Tests: PRO_IMAGE / PRO_AUDIO / PRO_LYRIA gate _select_media_type."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.cron_wiring import _pro_media_allowed


class TestProMediaAllowed:
    def _policy_file(self, tmp_path: Path, data: dict) -> Path:
        p = tmp_path / "delivery_policy.json"
        p.write_text(json.dumps(data))
        return p

    def _patch(self, policy_file: Path):
        mock_reg = MagicMock()
        mock_reg._delivery_policy_path.return_value = policy_file
        return patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg)

    def test_pro_image_zero_blocks(self, tmp_path: Path) -> None:
        pf = self._policy_file(tmp_path, {"PRO_IMAGE": 0})
        with self._patch(pf):
            assert _pro_media_allowed("s1", "image") is False

    def test_pro_audio_zero_blocks(self, tmp_path: Path) -> None:
        pf = self._policy_file(tmp_path, {"PRO_AUDIO": 0})
        with self._patch(pf):
            assert _pro_media_allowed("s1", "voice") is False

    def test_pro_lyria_zero_blocks(self, tmp_path: Path) -> None:
        pf = self._policy_file(tmp_path, {"PRO_LYRIA": 0})
        with self._patch(pf):
            assert _pro_media_allowed("s1", "music") is False

    def test_pro_image_two_allows(self, tmp_path: Path) -> None:
        pf = self._policy_file(tmp_path, {"PRO_IMAGE": 2})
        with self._patch(pf):
            assert _pro_media_allowed("s1", "image") is True

    def test_missing_policy_fails_open(self, tmp_path: Path) -> None:
        mock_reg = MagicMock()
        mock_reg._delivery_policy_path.return_value = tmp_path / "nope.json"
        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg):
            assert _pro_media_allowed("s1", "image") is True
