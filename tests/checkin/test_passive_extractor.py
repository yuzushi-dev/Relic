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
