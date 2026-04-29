import importlib
import os
import sys


def _purge_brand_modules() -> None:
    for name in list(sys.modules):
        if name == "mnemon" or name.startswith("mnemon."):
            sys.modules.pop(name, None)


def test_mnemon_package_exposes_runtime_modules():
    _purge_brand_modules()

    demo_runner = importlib.import_module("mnemon.demo_runner")
    webui = importlib.import_module("mnemon.webui")
    checkin = importlib.import_module("mnemon.checkin")

    assert hasattr(demo_runner, "run_demo")
    assert hasattr(webui, "main")
    assert hasattr(checkin, "main")
    assert demo_runner.__file__.endswith("/mnemon/demo_runner.py")
    assert webui.__file__.endswith("/mnemon/webui.py")
    assert checkin.__file__.endswith("/mnemon/checkin.py")


def test_relic_env_aliases_seed_legacy_runtime(monkeypatch):
    _purge_brand_modules()
    monkeypatch.delenv("RELIC_DATA_DIR", raising=False)
    monkeypatch.delenv("RELIC_SUBJECT_ID", raising=False)
    monkeypatch.setenv("RELIC_DATA_DIR", "/tmp/relic-demo")
    monkeypatch.setenv("RELIC_SUBJECT_ID", "relic-subject")

    importlib.import_module("mnemon")

    assert os.environ["RELIC_DATA_DIR"] == "/tmp/relic-demo"
    assert os.environ["RELIC_SUBJECT_ID"] == "relic-subject"
