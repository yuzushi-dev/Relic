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
