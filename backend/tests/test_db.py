from datetime import date

from app import db
from app.vault.tasks import Task

DAY1 = date(2026, 10, 5)
DAY2 = date(2026, 10, 6)


def task(text: str, done: bool) -> Task:
    return Task(
        id=text, text=text, done=done, project="P", section=None, parent=None,
        priority=3, overdue=False, notes=["n.md"],
    )


def test_first_sync_is_baseline_only(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        assert db.sync_tasks(conn, [task("a", True), task("b", False)], DAY1) == 0
        assert db.activity_by_day(conn) == {}


def test_completed_task_logs_activity_once(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        db.sync_tasks(conn, [task("a", False)], DAY1)
        assert db.sync_tasks(conn, [task("a", True)], DAY2) == 1
        assert db.sync_tasks(conn, [task("a", True)], DAY2) == 0
        assert db.activity_by_day(conn) == {DAY2: 1}
        assert db.recent_activity(conn, DAY1)[0]["detail"] == "a"


def test_new_task_already_done_counts_after_baseline(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        db.sync_tasks(conn, [task("a", False)], DAY1)
        assert db.sync_tasks(conn, [task("a", False), task("ya hice b", True)], DAY2) == 1


def test_reopened_task_does_not_count(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        db.sync_tasks(conn, [task("a", True)], DAY1)
        assert db.sync_tasks(conn, [task("a", False)], DAY2) == 0


def test_briefing_cache_and_refresh_counter(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        db.save_briefing(conn, DAY1, "hola", "m", refreshed=False)
        db.save_briefing(conn, DAY1, "hola 2", "m", refreshed=True)
        row = db.get_briefing(conn, DAY1)
        assert (row["content"], row["refreshes"]) == ("hola 2", 1)
        assert db.get_briefing(conn, DAY2) is None


def test_tracking_since_is_first_sync_day(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        assert db.tracking_since(conn) is None
        db.sync_tasks(conn, [task("a", False)], DAY1)
        db.sync_tasks(conn, [task("a", False), task("b", False)], DAY2)
        assert db.tracking_since(conn) == DAY1
