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
