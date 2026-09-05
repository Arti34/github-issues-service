def test_storage_round_trip(tmp_path, monkeypatch):
    import app.storage as s
    monkeypatch.setattr(s, "DB_PATH", str(tmp_path / "events.db"))
    s.init_db()
    assert s.save_event("d1", "issues", "opened", 1)
    assert not s.save_event("d1", "issues", "opened", 1)
    assert s.list_events(10)[0]["id"] == "d1"
