from relic.checkin.db_init import init_db
from relic.checkin.passive_state import get_watermark, set_watermark


def test_watermark_defaults_to_zero(tmp_path):
    conn = init_db(tmp_path / "r.db")
    assert get_watermark(conn, "daniele") == 0.0


def test_watermark_roundtrip_monotonic(tmp_path):
    conn = init_db(tmp_path / "r.db")
    set_watermark(conn, "daniele", 100.0)
    assert get_watermark(conn, "daniele") == 100.0
    set_watermark(conn, "daniele", 50.0)   # never moves backward
    assert get_watermark(conn, "daniele") == 100.0
