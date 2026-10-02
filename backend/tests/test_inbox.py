import shutil
from datetime import date

from app import db
from app.config import get_settings
from app.main import app
from app.vault.inbox import Capture, collect_captures

TODAY = date(2026, 10, 6)


def write_capture(inbox, name, created, title="Hice algo", origin="mascota"):
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(
        f'---\norigen: {origin}\ntipo: captura\ncreado: {created}\ntitulo: "{title}"\n---\n# {title}\n',
        encoding="utf-8",
    )


def test_collect_captures_reads_only_pet_notes(tmp_path):
    inbox = tmp_path / "00-Inbox"
    write_capture(inbox, "2026-10-05 2130 - Lab de S3.md", "2026-10-05T21:30:00-05:00", "Lab de S3")
    write_capture(inbox, "idea.md", "2026-10-05T10:00:00-05:00", origin="movil")
    (inbox / "_LEEME.md").write_text("# Inbox\n", encoding="utf-8")
    (inbox / "sin frontmatter.md").write_text("una idea suelta\n", encoding="utf-8")

    (capture,) = collect_captures(tmp_path, TODAY)
    assert capture == Capture(ref="2026-10-05 2130 - Lab de S3.md", title="Lab de S3", day=date(2026, 10, 5))


def test_capture_day_is_the_local_date_as_written(tmp_path):
    # 23:30 in Bogotá is already the next day in UTC: it must still count on the 5th.
    write_capture(tmp_path / "00-Inbox", "a.md", "2026-10-05T23:30:00-05:00")
    assert collect_captures(tmp_path, TODAY)[0].day == date(2026, 10, 5)


def test_future_capture_counts_as_today(tmp_path):
    write_capture(tmp_path / "00-Inbox", "a.md", "2026-10-09T08:00:00-05:00")
    assert collect_captures(tmp_path, TODAY)[0].day == TODAY


def test_capture_without_valid_date_is_ignored(tmp_path):
    write_capture(tmp_path / "00-Inbox", "a.md", "ayer")
    assert collect_captures(tmp_path, TODAY) == []


def test_no_inbox_folder(tmp_path):
    assert collect_captures(tmp_path, TODAY) == []


def test_sync_captures_logs_once_and_caps_per_day(tmp_path):
    captures = [Capture(ref=f"{i}.md", title=f"c{i}", day=TODAY) for i in range(7)]
    with db.connect(tmp_path / "t.db") as conn:
        assert db.sync_captures(conn, captures, max_per_day=5) == 5
        assert db.sync_captures(conn, captures, max_per_day=5) == 0
        assert db.activity_by_day(conn) == {TODAY: 5}


def test_processed_capture_keeps_its_activity(tmp_path):
    capture = Capture(ref="a.md", title="Lab", day=TODAY)
    with db.connect(tmp_path / "t.db") as conn:
        db.sync_captures(conn, [capture], max_per_day=5)
        db.sync_captures(conn, [], max_per_day=5)  # the agent emptied the Inbox
        assert db.activity_by_day(conn) == {TODAY: 1}
        assert db.recent_activity(conn, TODAY)[0] == {"day": "2026-10-06", "kind": "capture", "detail": "Lab"}


def test_capture_feeds_the_pet(client, settings, tmp_path):
    vault = tmp_path / "vault"
    shutil.copytree(settings.vault_path, vault)
    settings.vault_path = vault
    app.dependency_overrides[get_settings] = lambda: settings

    before = client.get("/pet").json()
    write_capture(vault / "00-Inbox", "2026-10-06 0900 - Lab.md", "2026-10-06T09:00:00-05:00", "Lab")
    after = client.get("/pet").json()

    assert after["xp"] == before["xp"] + 10
    assert after["energy"] == 100
    assert after["streak"] >= 1
