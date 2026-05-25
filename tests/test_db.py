import db


def test_init_db_creates_tables(tmp_db):
    conn = db.get_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "api_keys" in tables
    assert "reports" in tables


def test_add_and_get_key(tmp_db):
    key_id = db.add_key(user_id=1, label="Магазин 1", api_key="secret-token")
    rows = db.get_keys(user_id=1)
    assert len(rows) == 1
    assert rows[0]["label"] == "Магазин 1"
    assert db.decrypt_key(rows[0]) == "secret-token"


def test_get_key_by_id(tmp_db):
    key_id = db.add_key(user_id=1, label="Shop", api_key="tok")
    row = db.get_key(key_id)
    assert row is not None
    assert row["id"] == key_id


def test_new_key_is_valid_by_default(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    assert db.get_key(key_id)["is_valid"] == 1


def test_update_key_validity(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    db.update_key_validity(key_id, False)
    assert db.get_key(key_id)["is_valid"] == 0
    db.update_key_validity(key_id, True)
    assert db.get_key(key_id)["is_valid"] == 1


def test_delete_key_cascades(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    db.upsert_report(key_id, 101, "2026-01-01", "2026-01-07", 1, 1000.0)
    db.delete_key(key_id)
    conn = db.get_conn()
    reports = conn.execute(
        "SELECT * FROM reports WHERE key_id=?", (key_id,)
    ).fetchall()
    conn.close()
    assert reports == []


def test_upsert_report_deduplicates(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    db.upsert_report(key_id, 101, "2026-01-01", "2026-01-07", 1, 1000.0)
    db.upsert_report(key_id, 101, "2026-01-01", "2026-01-07", 1, 1500.0)
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM reports WHERE key_id=?", (key_id,)
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["retail_amount_sum"] == 1500.0


def test_get_reports_for_period_filters_by_date_to(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    # date_to попадает в январь → входит в январь
    db.upsert_report(key_id, 1, "2025-12-25", "2026-01-04", 1, 500.0)
    # date_to в январе
    db.upsert_report(key_id, 2, "2026-01-05", "2026-01-11", 1, 600.0)
    # date_to в феврале → не входит в январь
    db.upsert_report(key_id, 3, "2026-01-26", "2026-02-01", 1, 700.0)

    reports = db.get_reports_for_period(key_id, (2026, 1), (2026, 1))
    assert len(reports) == 2
    amounts = {r["retail_amount_sum"] for r in reports}
    assert amounts == {500.0, 600.0}


def test_get_reports_for_period_multi_month(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    db.upsert_report(key_id, 1, "2026-01-01", "2026-01-07", 1, 100.0)
    db.upsert_report(key_id, 2, "2026-02-01", "2026-02-07", 1, 200.0)
    db.upsert_report(key_id, 3, "2026-03-01", "2026-03-07", 1, 300.0)
    db.upsert_report(key_id, 4, "2026-04-01", "2026-04-07", 1, 400.0)

    reports = db.get_reports_for_period(key_id, (2026, 1), (2026, 3))
    assert len(reports) == 3


def test_update_last_synced(tmp_db):
    key_id = db.add_key(user_id=1, label="X", api_key="y")
    assert db.get_key(key_id)["last_synced_at"] is None
    db.update_last_synced(key_id)
    assert db.get_key(key_id)["last_synced_at"] is not None
