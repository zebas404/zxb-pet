"""Captures: "ya hice X" notes the desktop shell creates in the vault Inbox.

The shell writes them with ``origen: mascota`` and a ``creado`` timestamp. They count
as activity on the day they were created. Once the vault agent processes the Inbox the
notes disappear, but the activity is already stored in SQLite.
"""

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel

from .markdown import try_read_note

INBOX_FOLDER = "00-Inbox"
ORIGIN = "mascota"


class Capture(BaseModel):
    ref: str  # file name, unique per capture (the shell prefixes a timestamp)
    title: str
    day: date


def _created_day(value) -> date | None:
    # YAML turns "2026-10-01T19:02:22-05:00" into an aware datetime; .date() keeps
    # the local date as written by the PC.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def collect_captures(root: Path, today: date) -> list[Capture]:
    """Pet captures at the top level of the Inbox. Future dates (clock skew) count as today."""
    inbox = root / INBOX_FOLDER
    if not inbox.is_dir():
        return []
    captures: list[Capture] = []
    for path in sorted(inbox.glob("*.md")):
        note = try_read_note(path, root)
        if not note or str(note.frontmatter.get("origen", "")).strip().lower() != ORIGIN:
            continue
        day = _created_day(note.frontmatter.get("creado"))
        if day is None:
            continue
        title = str(note.frontmatter.get("titulo") or path.stem).strip()
        captures.append(Capture(ref=path.name, title=title, day=min(day, today)))
    return captures
