def test_load_new_messages_filters_and_cleans(tmp_path):
    state = tmp_path / "state.db"
    import sqlite3
    c = sqlite3.connect(state)
    c.execute("CREATE TABLE messages (role TEXT, content TEXT, timestamp REAL)")
    c.executemany("INSERT INTO messages VALUES (?,?,?)", [
        ("user", "[IMPORTANT: cron prompt]", 10),
        ("assistant", "ciao", 11),
        ("user", "ok", 12),                                   # too short / dismissal
        ("user", '[Replying to: "x"] Ho corso un grosso rischio oggi', 13),
        ("user", "Mi sono fermato a riflettere sulla giornata", 20),
    ])
    c.commit(); c.close()
    from relic.checkin.passive_extractor import load_new_messages
    msgs = load_new_messages(state, since_ts=5.0)
    texts = [m["text"] for m in msgs]
    assert texts == ["Ho corso un grosso rischio oggi", "Mi sono fermato a riflettere sulla giornata"]
    assert msgs[-1]["ts"] == 20


def _facets(conn):
    return {r[0]: {"name": r[1], "description": r[2], "spectrum_low": r[3], "spectrum_high": r[4]}
            for r in conn.execute("SELECT id,name,description,spectrum_low,spectrum_high FROM facets")}


def test_attribute_message_jury_picks_facet(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import attribute_message
    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    target = "cognitive.risk_tolerance"
    assert target in facets
    # fake panel: every judge always votes the target -> majority + all families
    fake = lambda model, reply, question, candidates, **kw: target
    got = attribute_message("ho corso un grosso rischio", facets, judge_fn=fake)
    assert got == target


def test_attribute_message_none_when_panel_abstains(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import attribute_message
    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    fake = lambda *a, **k: "NONE"
    assert attribute_message("ciao come va oggi", facets, judge_fn=fake) is None


def test_extract_and_write_strong_signal_writes_observation(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import extract_and_write
    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    facet_id = "cognitive.risk_tolerance"
    assert facet_id in facets
    # fake llm_client matches the extract_observation seam: (system, prompt) -> parsed JSON dict
    fake_llm = lambda system, prompt: {
        "informative": True,
        "signal_position": 0.85,
        "signal_strength": 0.9,
        "observation_summary": "ha corso un grosso rischio oggi",
        "confidence_delta": 0.2,
    }
    res = extract_and_write(
        conn, facet_id, facets, "ho corso un grosso rischio oggi", 1700000000.0,
        llm_client=fake_llm,
    )
    assert res["written"] is True
    assert res["facet_id"] == facet_id

    rows = conn.execute(
        "SELECT facet_id, source_type, source_ref FROM observations "
        "WHERE source_type='passive_chat'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == facet_id
    assert rows[0][1] == "passive_chat"
    assert rows[0][2] == "msg:1700000000"


def test_extract_and_write_weak_signal_writes_nothing(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import extract_and_write
    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    facet_id = "cognitive.risk_tolerance"
    # below the strength floor -> dropped, nothing written
    fake_llm = lambda system, prompt: {
        "informative": True,
        "signal_position": 0.5,
        "signal_strength": 0.2,
        "observation_summary": "segnale debole",
        "confidence_delta": 0.1,
    }
    res = extract_and_write(
        conn, facet_id, facets, "forse, non saprei", 1700000001.0,
        llm_client=fake_llm,
    )
    assert res["written"] is False
    assert res["reason"] == "weak_signal"
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


def _build_state_db(path, rows):
    import sqlite3
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE messages (role TEXT, content TEXT, timestamp REAL)")
    c.executemany("INSERT INTO messages VALUES (?,?,?)", rows)
    c.commit()
    c.close()


def _write_policy(tmp_path, subject_id, consent):
    import json
    base = tmp_path / "subjects" / subject_id
    base.mkdir(parents=True, exist_ok=True)
    dp = base / "delivery_policy.json"
    payload = {} if consent is None else {"consent_for_passive_extraction": consent}
    dp.write_text(json.dumps(payload), encoding="utf-8")
    return dp


def test_run_passive_extraction_end_to_end(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import run_passive_extraction

    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    target = "cognitive.risk_tolerance"
    assert target in facets

    state = tmp_path / "state.db"
    _build_state_db(state, [
        ("user", "ho corso un grosso rischio oggi", 100.0),
        ("user", "ho corso un altro rischio nelle mie scelte", 200.0),
    ])
    _write_policy(tmp_path, "daniele", True)

    fake_judge = lambda model, reply, question, candidates, **kw: target
    fake_llm = lambda system, prompt: {
        "informative": True,
        "signal_position": 0.85,
        "signal_strength": 0.9,
        "observation_summary": "ha corso un grosso rischio",
        "confidence_delta": 0.2,
    }

    res = run_passive_extraction(
        conn, "daniele", state, facets,
        relic_home=tmp_path, judge_fn=fake_judge, llm_client=fake_llm,
    )
    assert res["processed"] == 2
    assert res["attributed"] == 2
    assert res["written"] == 2
    assert res["watermark"] == 200.0

    rows = conn.execute(
        "SELECT facet_id, source_type FROM observations WHERE source_type='passive_chat'"
    ).fetchall()
    assert len(rows) == 2
    assert all(r[0] == target and r[1] == "passive_chat" for r in rows)

    # Second run: watermark already at 200.0, no new messages -> nothing happens.
    res2 = run_passive_extraction(
        conn, "daniele", state, facets,
        relic_home=tmp_path, judge_fn=fake_judge, llm_client=fake_llm,
    )
    assert res2["processed"] == 0
    assert res2["written"] == 0
    assert res2["watermark"] == 200.0
    assert conn.execute(
        "SELECT COUNT(*) FROM observations WHERE source_type='passive_chat'"
    ).fetchone()[0] == 2


def test_run_passive_extraction_no_consent_short_circuits(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import run_passive_extraction

    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)

    state = tmp_path / "state.db"
    _build_state_db(state, [
        ("user", "ho corso un grosso rischio oggi", 100.0),
    ])

    def _boom(*a, **k):  # must never be called when consent is absent
        raise AssertionError("messages must not be read without consent")

    # consent explicitly False
    _write_policy(tmp_path, "daniele", False)
    res = run_passive_extraction(
        conn, "daniele", state, facets,
        relic_home=tmp_path, judge_fn=_boom, llm_client=_boom,
    )
    assert res == {"skipped": "no_consent"}

    # flag missing entirely -> still no consent
    _write_policy(tmp_path, "daniele", None)
    res_missing = run_passive_extraction(
        conn, "daniele", state, facets,
        relic_home=tmp_path, judge_fn=_boom, llm_client=_boom,
    )
    assert res_missing == {"skipped": "no_consent"}

    # policy file absent -> still no consent
    res_absent = run_passive_extraction(
        conn, "barbara", state, facets,
        relic_home=tmp_path, judge_fn=_boom, llm_client=_boom,
    )
    assert res_absent == {"skipped": "no_consent"}

    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Task 7: run_for_hermes_home (single-subject cron entrypoint) + CLI
# ---------------------------------------------------------------------------

def _setup_subject(tmp_path, sid, *, consent, messages):
    """Build a subject's own relic.db (+policy) and a gumi-<sid> hermes_home
    with its own state.db. Returns (hermes_home, relic_home, relic_db)."""
    import sqlite3
    import json
    from relic.checkin.db_init import init_db, seed_facets

    relic_home = tmp_path / "relic"
    subj_dir = relic_home / "subjects" / sid
    subj_dir.mkdir(parents=True)
    relic_db = subj_dir / "relic.db"
    conn = init_db(relic_db)
    seed_facets(conn)
    conn.close()

    if consent is not None:
        (subj_dir / "delivery_policy.json").write_text(
            json.dumps({"consent_for_passive_extraction": consent}),
            encoding="utf-8",
        )

    hermes_home = tmp_path / f"gumi-{sid}"
    hermes_home.mkdir()
    if messages is not None:
        _build_state_db(hermes_home / "state.db", messages)
    return hermes_home, relic_home, relic_db


def test_run_for_hermes_home_happy_path(tmp_path, monkeypatch):
    import sqlite3
    from relic.checkin import passive_extractor

    sid = "daniele"
    target = "cognitive.risk_tolerance"
    hermes_home, relic_home, relic_db = _setup_subject(
        tmp_path, sid, consent=True, messages=[
            ("user", "ho corso un grosso rischio nelle mie scelte", 100.0),
            ("user", "ho deciso di rischiare ancora una volta oggi", 200.0),
        ],
    )

    # Network-free: the jury and the signal writer are the only seams that
    # would hit the LLM; replace them at the module level (run_passive_extraction
    # calls both by bare global name).
    monkeypatch.setattr(
        passive_extractor, "attribute_message",
        lambda text, facets, **kw: target,
    )

    def _fake_write(conn, facet_id, facets, text, ts, **kw):
        conn.execute(
            "INSERT OR IGNORE INTO observations "
            "(facet_id, source_type, source_ref, content, extracted_signal, "
            "signal_strength, signal_position, created_at) "
            "VALUES (?, 'passive_chat', ?, ?, ?, ?, ?, ?)",
            (facet_id, f"msg:{int(ts)}", "obs", "{}", 0.9, 0.8, "now"),
        )
        conn.commit()
        return {"written": True, "facet_id": facet_id}

    monkeypatch.setattr(passive_extractor, "extract_and_write", _fake_write)

    # subject_id NOT passed -> derived from "gumi-daniele" dir name.
    res = passive_extractor.run_for_hermes_home(hermes_home, relic_home=relic_home)

    assert res["subject_id"] == sid
    assert res["processed"] == 2     # both messages came from <hermes_home>/state.db
    assert res["attributed"] == 2
    assert res["written"] == 2
    assert res["watermark"] == 200.0

    # Observations landed under the subject's OWN relic.db.
    check = sqlite3.connect(str(relic_db))
    rows = check.execute(
        "SELECT facet_id, source_type FROM observations WHERE source_type='passive_chat'"
    ).fetchall()
    check.close()
    assert len(rows) == 2
    assert all(r[0] == target and r[1] == "passive_chat" for r in rows)


def test_run_for_hermes_home_skips_without_state_db(tmp_path, monkeypatch):
    import sqlite3
    from relic.checkin import passive_extractor

    sid = "daniele"
    # consent ON and relic.db present, but NO state.db under hermes_home.
    hermes_home, relic_home, relic_db = _setup_subject(
        tmp_path, sid, consent=True, messages=None,
    )

    def _boom(*a, **k):
        raise AssertionError("must not read/process when subject unresolved")

    monkeypatch.setattr(passive_extractor, "load_new_messages", _boom)
    monkeypatch.setattr(passive_extractor, "attribute_message", _boom)

    res = passive_extractor.run_for_hermes_home(hermes_home, relic_home=relic_home)
    assert res == {"skipped": "unresolved_subject", "subject_id": sid}

    # Nothing written.
    check = sqlite3.connect(str(relic_db))
    n = check.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    check.close()
    assert n == 0


def test_run_for_hermes_home_skips_when_subject_relic_db_missing(tmp_path, monkeypatch):
    from relic.checkin import passive_extractor

    def _boom(*a, **k):
        raise AssertionError("must not read when subject relic.db is missing")

    monkeypatch.setattr(passive_extractor, "load_new_messages", _boom)

    # state.db exists, but there is no subjects/<sid>/relic.db at all.
    hermes_home = tmp_path / "gumi-ghost"
    hermes_home.mkdir()
    _build_state_db(hermes_home / "state.db", [
        ("user", "ho corso un grosso rischio", 1.0),
    ])
    relic_home = tmp_path / "relic"  # no subjects dir -> unresolvable subject

    res = passive_extractor.run_for_hermes_home(hermes_home, relic_home=relic_home)
    assert res == {"skipped": "unresolved_subject", "subject_id": "ghost"}


def test_main_cli_dry_run_smoke(tmp_path, monkeypatch, capsys):
    import json
    import sqlite3
    from relic.checkin import passive_extractor

    sid = "daniele"
    hermes_home, relic_home, relic_db = _setup_subject(
        tmp_path, sid, consent=True, messages=[
            ("user", "ho corso un grosso rischio nelle mie scelte", 100.0),
        ],
    )

    # Keep network-free even on the dry path (extract_and_write would still
    # call the LLM extractor under dry_run, so stub both seams).
    monkeypatch.setattr(
        passive_extractor, "attribute_message",
        lambda *a, **k: "cognitive.risk_tolerance",
    )
    monkeypatch.setattr(
        passive_extractor, "extract_and_write",
        lambda *a, **k: {"written": False, "reason": "dry"},
    )

    monkeypatch.setattr("sys.argv", [
        "passive_extractor",
        "--hermes-home", str(hermes_home),
        "--relic-home", str(relic_home),
        "--subject-id", sid,
        "--dry-run",
    ])

    rc = passive_extractor.main()
    assert rc == 0

    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["subject_id"] == sid

    # Dry-run writes nothing.
    check = sqlite3.connect(str(relic_db))
    n = check.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    check.close()
    assert n == 0


def test_run_for_hermes_home_refuses_subject_mismatch(tmp_path):
    """Privacy guard: if the requested subject disagrees with the hermes_home
    owner, refuse — state.db belongs to a different subject than the relic.db."""
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import run_for_hermes_home

    hermes_home = tmp_path / "profiles" / "gumi-daniele"
    hermes_home.mkdir(parents=True)
    import sqlite3
    s = sqlite3.connect(hermes_home / "state.db")
    s.execute("CREATE TABLE messages (role TEXT, content TEXT, timestamp REAL)")
    s.execute("INSERT INTO messages VALUES ('user','ho corso un grosso rischio nelle scelte',100)")
    s.commit(); s.close()

    relic_home = tmp_path / "relic"
    for sid in ("daniele", "barbara"):
        d = relic_home / "subjects" / sid
        d.mkdir(parents=True)
        c = init_db(d / "relic.db"); seed_facets(c); c.close()
        (d / "delivery_policy.json").write_text('{"consent_for_passive_extraction": true}')

    # hermes_home owner = daniele, but caller asks for barbara → must refuse.
    res = run_for_hermes_home(hermes_home, relic_home=relic_home, subject_id="barbara")
    assert res.get("skipped") == "subject_mismatch", res
    # no observations written to either subject
    for sid in ("daniele", "barbara"):
        c = sqlite3.connect(relic_home / "subjects" / sid / "relic.db")
        n = c.execute("SELECT COUNT(*) FROM observations WHERE source_type='passive_chat'").fetchone()[0]
        c.close()
        assert n == 0
