from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_contains_public_package_metadata():
    pyproject = ROOT / "pyproject.toml"
    assert pyproject.exists()
    text = pyproject.read_text(encoding="utf-8")
    assert 'name = "relic"' in text
    assert 'relic-demo = "relic.demo_runner:main"' in text
    assert 'relic-demo-ui = "relic.demo_webui:main"' in text
    assert 'relic-webui = "relic.webui:main"' in text
    assert 'package-dir = {"" = "src"}' in text


def test_runtime_naming_doc_exists():
    doc = ROOT / "docs" / "PUBLIC_RUNTIME.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "event_log.sample.jsonl" in text
    assert "delivery_log.sample.jsonl" in text
    assert "model_profile.md" in text
