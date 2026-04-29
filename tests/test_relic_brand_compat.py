import importlib
import os
import sys


def _purge_brand_modules() -> None:
    for name in list(sys.modules):
        if name == "relic" or name.startswith("relic.") or name == "relic":
            sys.modules.pop(name, None)


def test_relic_package_exposes_legacy_runtime_modules():
    _purge_brand_modules()

    demo_runner = importlib.import_module("relic.demo_runner")
    webui = importlib.import_module("relic.webui")
    checkin = importlib.import_module("relic.checkin")

    assert hasattr(demo_runner, "run_demo")
    assert hasattr(webui, "main")
    assert hasattr(checkin, "main")
    assert demo_runner.__file__.endswith("/relic/demo_runner.py")
    assert webui.__file__.endswith("/relic/webui.py")
    assert checkin.__file__.endswith("/relic/checkin.py")


def test_relic_env_aliases_seed_legacy_runtime(monkeypatch):
    _purge_brand_modules()
    monkeypatch.delenv("RELIC_DATA_DIR", raising=False)
    monkeypatch.delenv("RELIC_SUBJECT_ID", raising=False)
    monkeypatch.setenv("RELIC_DATA_DIR", "/tmp/relic-demo")
    monkeypatch.setenv("RELIC_SUBJECT_ID", "relic-subject")

    importlib.import_module("relic")

    assert os.environ["RELIC_DATA_DIR"] == "/tmp/relic-demo"
    assert os.environ["RELIC_SUBJECT_ID"] == "relic-subject"
