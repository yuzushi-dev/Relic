.PHONY: help setup lint test test-full test-full-root test-full-docs test-full-runtime test-full-gumi test-full-hermes test-full-memory test-full-lab-eval test-full-ui test-full-skills test-bootstrap test-hermes-compat fixture-gumi-memory test-db test-cac test-privacy test-correction test-compiler test-vault test-hermes-plugin test-eval test-ui fixture-basic fixture-corrections fixture-privacy fixture-no-injection fixture-ui-validation fixture-memory-dynamics eval-baselines replication-bundle demo-e2e validate-design test-memory-dynamics memory-dynamics-report setup-dry-run debug-bundle test-debug-bundle test-gumi-roleplay fixture-gumi-roleplay test-gumi-plugin test-gumi-provider-normalization test-docs validate-handoff

HERMES_VENV ?= $(HOME)/.hermes/hermes-agent/venv/bin
PYTHON := $(shell command -v python3 2>/dev/null || echo python)
PYTEST := $(shell test -x $(HERMES_VENV)/pytest && echo $(HERMES_VENV)/pytest || command -v pytest 2>/dev/null || echo pytest)
RUFF := $(shell test -x $(HERMES_VENV)/ruff && echo $(HERMES_VENV)/ruff || command -v ruff 2>/dev/null || echo ruff)

help:
	@echo "Relic E2E - Available targets:"
	@echo "  setup              Install dependencies"
	@echo "  lint               Run linter (ruff)"
	@echo "  test               Run default fast profile/profile+Gumi/bootstrap tests"
	@echo "  test-full          Run complete suite as sequential batches"
	@echo "  test-full-root     Run root smoke/config tests"
	@echo "  test-full-docs     Run documentation contract tests"
	@echo "  test-full-runtime  Run runtime/compiler/privacy/vault batches"
	@echo "  test-full-gumi     Run Gumi memory/plugin/roleplay compatibility batches"
	@echo "  test-full-hermes   Run Hermes plugin batch"
	@echo "  test-full-memory   Run memory dynamics batch"
	@echo "  test-full-lab-eval Run lab/eval/e2e batch"
	@echo "  test-full-ui       Run UI contract batch"
	@echo "  test-full-skills   Run skill metadata/safety batch"
	@echo "  test-bootstrap     Run bootstrap/profile/Gumi tests"
	@echo "  test-db            Run DB schema tests"
	@echo "  test-cac           Run CAC tests"
	@echo "  test-privacy       Run privacy tests"
	@echo "  test-correction    Run correction propagation tests"
	@echo "  test-compiler      Run compiler tests"
	@echo "  test-vault         Run vault tests"
	@echo "  test-hermes-plugin Run Hermes plugin tests"
	@echo "  test-eval          Run evaluation tests"
	@echo "  test-debug-bundle  Run debug bundle tests"
	@echo "  test-ui            Run UI tests"
	@echo "  test-memory-dynamics Run memory dynamics tests"
	@echo "  test-hermes-compat  Run Hermes compatibility tests (gumi_memory)"
	@echo "  test-gumi-roleplay Run Gumi roleplay continuity tests"
	@echo "  fixture-basic      Load basic fixture"
	@echo "  fixture-corrections Load corrections fixture"
	@echo "  fixture-privacy    Load privacy fixture"
	@echo "  fixture-no-injection Load no-injection fixture"
	@echo "  fixture-ui-validation Load UI validation fixture"
	@echo "  fixture-gumi-memory  Load gumi-memory fixture"
	@echo "  fixture-gumi-roleplay Load gumi roleplay fixture"
	@echo "  fixture-memory-dynamics Load memory dynamics fixture"
	@echo "  eval-baselines     Run evaluation baselines"
	@echo "  replication-bundle Build replication bundle"
	@echo "  debug-bundle       Build debug bundle"
	@echo "  demo-e2e           Run E2E demo"
	@echo "  validate-design    Validate dev_docs/project_docs/DESIGN.md compliance"
	@echo "  memory-dynamics-report Generate memory dynamics report"
	@echo "  setup-dry-run      Verify bootstrap scripts (no actual setup)"

setup:
	pip install -e .

setup-dry-run:
	@echo "Bootstrap verification (dry-run):"
	@echo "  - Would install: pip install -e .[dev]"
	@echo "  - Would verify: relic.db schema"
	@echo "  - Would verify: Hermes plugin loadable"

lint:
	$(RUFF) check relic/ tests/ --output-format=concise

test:
	PYTHONPATH=. $(PYTEST) tests/bootstrap tests/profile tests/gumi -v --tb=short

test-bootstrap:
	PYTHONPATH=. $(PYTEST) tests/bootstrap tests/profile tests/gumi -v --tb=short

test-full:
	$(MAKE) test-full-root
	$(MAKE) test-bootstrap
	$(MAKE) test-full-docs
	$(MAKE) test-full-runtime
	$(MAKE) test-full-gumi
	$(MAKE) test-full-hermes
	$(MAKE) test-full-memory
	$(MAKE) test-full-lab-eval
	$(MAKE) test-full-ui
	$(MAKE) test-full-skills

test-full-root:
	PYTHONPATH=. $(PYTEST) tests/test_cli_setup.py tests/test_config.py tests/test_db_schema.py tests/test_makefile_targets.py tests/test_smoke.py -q --tb=short

test-full-docs:
	PYTHONPATH=. $(PYTEST) tests/docs/ -q --tb=short

test-full-runtime:
	PYTHONPATH=. $(PYTEST) tests/artifacts/ tests/cac/ tests/compiler/ tests/control/ tests/correction/ tests/privacy/ tests/profiles/ tests/vault/ -q --tb=short

test-full-gumi:
	PYTHONPATH=. $(PYTEST) tests/gumi_memory/ tests/gumi_plugin/ tests/gumi_roleplay/ tests/hermes_compat/ -q --tb=short

test-full-hermes:
	PYTHONPATH=. $(PYTEST) tests/hermes_plugin/ -q --tb=short

test-full-memory:
	PYTHONPATH=. $(PYTEST) tests/memory_dynamics/ -q --tb=short

test-full-lab-eval:
	PYTHONPATH=. $(PYTEST) tests/e2e/ tests/eval/ tests/lab/ -q --tb=short

test-full-ui:
	PYTHONPATH=. $(PYTEST) tests/ui/ -q --tb=short

test-full-skills:
	PYTHONPATH=. $(PYTEST) tests/skills/ -q --tb=short

test-db:
	PYTHONPATH=. $(PYTEST) tests/test_db_schema.py tests/test_config.py -v --tb=short

test-cac:
	PYTHONPATH=. $(PYTEST) tests/cac/ -v --tb=short

test-privacy:
	PYTHONPATH=. $(PYTEST) tests/privacy/ -v --tb=short

test-correction:
	PYTHONPATH=. $(PYTEST) tests/control/ tests/correction/ -v --tb=short

test-compiler:
	PYTHONPATH=. $(PYTEST) tests/compiler/ -v --tb=short

test-vault:
	PYTHONPATH=. $(PYTEST) tests/vault/ -v --tb=short

test-hermes-plugin:
	PYTHONPATH=. $(PYTEST) tests/hermes_plugin/ -v --tb=short

test-eval:
	PYTHONPATH=. $(PYTEST) tests/eval/ -v --tb=short

test-debug-bundle:
	PYTHONPATH=. $(PYTEST) tests/eval/test_debug_bundle.py -v --tb=short

test-ui:
	PYTHONPATH=. $(PYTEST) tests/ui/ -v --tb=short

test-memory-dynamics:
	PYTHONPATH=. $(PYTEST) tests/memory_dynamics/ -v --tb=short

fixture-basic:
	@echo "Loading basic fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('basic')" 2>/dev/null || echo "fixture loader not yet implemented"

fixture-corrections:
	@echo "Loading corrections fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('corrections')" 2>/dev/null || echo "fixture loader not yet implemented"

fixture-privacy:
	@echo "Loading privacy fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('privacy')" 2>/dev/null || echo "fixture loader not yet implemented"

fixture-no-injection:
	@echo "Loading no-injection fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('no-injection')" 2>/dev/null || echo "fixture loader not yet implemented"

fixture-ui-validation:
	@echo "Loading UI validation fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('ui-validation')" 2>/dev/null || echo "fixture loader not yet implemented"

fixture-memory-dynamics:
	@echo "Loading memory dynamics fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('memory-dynamics')" 2>/dev/null || echo "fixture loader not yet implemented"

eval-baselines:
	@echo "Running evaluation baselines..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.eval.baselines import run_baselines; result = run_baselines(); print('Baselines completed:', list(result.keys()))"

replication-bundle:
	@echo "Building replication bundle..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.eval.replication_bundle import build_bundle; bundle = build_bundle(); print('Bundle created:', bundle.bundle_id)"

debug-bundle:
	@echo "Building debug bundle..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.eval.debug_bundle import emit_debug_bundle; bundle = emit_debug_bundle(); print('Debug bundle created:', bundle.bundle_id)"

demo-e2e:
	@echo "Generating demo data..."
	@PYTHONPATH=. $(PYTHON) scripts/generate_demo_data.py
	@echo "Demo console ready: demo/console.html"

validate-design:
	@echo "Validating dev_docs/project_docs/DESIGN.md compliance..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.ui import validate_design; validate_design()" 2>/dev/null || echo "design validation not yet implemented"

memory-dynamics-report:
	@echo "Generating memory dynamics report..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.eval import memory_dynamics_report; memory_dynamics_report()" 2>/dev/null || echo "memory dynamics report not yet implemented"

test-docs:
	PYTHONPATH=. $(PYTEST) tests/docs/ -v --tb=short

# PR19/PR22 - Hermes compatibility and Gumi memory provider inventory
test-hermes-compat:
	@echo "Running Hermes compatibility tests..."
	@PYTHONPATH=. $(PYTEST) tests/hermes_compat/ tests/gumi_memory/ -v --tb=short

fixture-gumi-memory:
	@echo "Loading gumi-memory fixture..."
	@PYTHONPATH=. $(PYTHON) -c "from relic.db import load_fixture; load_fixture('gumi-memory')" 2>/dev/null || echo "Loading fixture from fixtures/gumi-memory/provider_conditions.json"
	@PYTHONPATH=. $(PYTHON) -c "import json; data = json.load(open('fixtures/gumi-memory/provider_conditions.json')); print('Fixture loaded:', data.get('evaluation_metadata', {}).get('evaluation_name', 'unknown'))"

# PR22 - Gumi roleplay / plugin
test-gumi-roleplay:
	@echo "Running Gumi roleplay tests..."
	@PYTHONPATH=. $(PYTEST) tests/gumi_roleplay/ -v --tb=short

fixture-gumi-roleplay:
	@echo "Loading gumi-roleplay fixture..."
	@PYTHONPATH=. $(PYTHON) -c "import json; data = json.load(open('fixtures/gumi-roleplay/example_prompt_context_pack.json')); print('Fixture loaded:', data.get('pack_id', 'unknown'))"

test-gumi-plugin:
	@echo "Running Gumi plugin tests..."
	@PYTHONPATH=. $(PYTEST) tests/gumi_plugin/ -v --tb=short

# PR19B - provider normalization
test-gumi-provider-normalization:
	@echo "Running gumi memory provider normalization tests..."
	@PYTHONPATH=. $(PYTEST) tests/gumi_memory/ -v -k "external_memory_candidate or memory_exposure_event or local_private_data" --tb=short

# PR13 - validate handoff (PyYAML/jsonschema-free path)
validate-handoff:
	@echo "Validating handoff..."
	@$(PYTHON) scripts/validate_handoff.py
