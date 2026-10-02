"""SQLite storage: task snapshots, activity log and the daily briefing cache."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from .vault.inbox import Capture
from .vault.tasks import Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_state (
    id         TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    done       INTEGER NOT NULL,
    first_seen TEXT NOT NULL,  -- local date the task was first seen
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    day    TEXT NOT NULL,
    kind   TEXT NOT NULL,
    ref    TEXT NOT NULL,
    detail TEXT,
    UNIQUE (day, kind, ref)
);
CREATE TABLE IF NOT EXISTS briefing (
    day        TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    model      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    refreshes  INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def sync_tasks(conn: sqlite3.Connection, tasks: list[Task], today: date) -> int:
    """Compare the vault against the last snapshot and log newly completed tasks.

    The very first sync only records the baseline, so existing ``[x]`` don't count as activity.
    Returns how many tasks were completed since the previous sync.
    """
    known = {row["id"]: bool(row["done"]) for row in conn.execute("SELECT id, done FROM task_state")}
    baseline = not known
    completed = 0
    now = _now()
    for task in tasks:
        before = known.get(task.id)
        if before is None:
            conn.execute(
                "INSERT OR IGNORE INTO task_state (id, text, done, first_seen, updated_at) VALUES (?, ?, ?, ?, ?)",
                (task.id, task.text, int(task.done), today.isoformat(), now),
            )
        elif before != task.done:
            conn.execute(
                "UPDATE task_state SET done = ?, text = ?, updated_at = ? WHERE id = ?",
                (int(task.done), task.text, now, task.id),
            )
        if task.done and not before and not baseline:
            completed += log_activity(conn, today, "task_done", task.id, task.text)
    return completed


def sync_captures(conn: sqlite3.Connection, captures: list[Capture], max_per_day: int) -> int:
    """Log Inbox captures as activity, at most ``max_per_day`` per day (no XP farming).

    Returns how many new captures were logged.
    """
    logged = 0
    for capture in captures:
        day = capture.day.isoformat()
        seen = conn.execute(
            "SELECT 1 FROM activity WHERE kind = 'capture' AND ref = ?", (capture.ref,)
        ).fetchone()
        if seen:
            continue
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM activity WHERE kind = 'capture' AND day = ?", (day,)
        ).fetchone()
        if count >= max_per_day:
            continue
        logged += log_activity(conn, capture.day, "capture", capture.ref, capture.title)
    return logged


def log_activity(conn: sqlite3.Connection, day: date, kind: str, ref: str, detail: str | None = None) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO activity (day, kind, ref, detail) VALUES (?, ?, ?, ?)",
        (day.isoformat(), kind, ref, detail),
    )
    return cur.rowcount


def activity_by_day(conn: sqlite3.Connection) -> dict[date, int]:
    rows = conn.execute("SELECT day, COUNT(*) AS n FROM activity GROUP BY day")
    return {date.fromisoformat(r["day"]): r["n"] for r in rows}


def tracking_since(conn: sqlite3.Connection) -> date | None:
    """Local date of the first sync: when Zebot started watching the vault."""
    row = conn.execute("SELECT MIN(first_seen) AS d FROM task_state").fetchone()
    return date.fromisoformat(row["d"][:10]) if row["d"] else None


def recent_activity(conn: sqlite3.Connection, since: date) -> list[dict]:
    rows = conn.execute(
        "SELECT day, kind, detail FROM activity WHERE day >= ? ORDER BY day DESC, id DESC LIMIT 20",
        (since.isoformat(),),
    )
    return [dict(r) for r in rows]


def get_briefing(conn: sqlite3.Connection, day: date) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM briefing WHERE day = ?", (day.isoformat(),)).fetchone()


def save_briefing(conn: sqlite3.Connection, day: date, content: str, model: str, refreshed: bool) -> None:
    conn.execute(
        """
        INSERT INTO briefing (day, content, model, created_at, refreshes) VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(day) DO UPDATE SET
            content = excluded.content, model = excluded.model, created_at = excluded.created_at,
            refreshes = briefing.refreshes + ?
        """,
        (day.isoformat(), content, model, _now(), int(refreshed)),
    )
