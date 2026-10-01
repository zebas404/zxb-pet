"""Find what to study today from ``Roadmap - …`` notes with dated phases."""

import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .markdown import Note, clean_text, iter_headings, iter_notes, parse_list_items, parse_phase_heading
from .tasks import project_name

ROADMAP_FOLDERS = ["01-Proyectos"]
PENDING_WIKI_RE = re.compile(r"\[\[([^\]|#]+)[^\]]*\]\]\s*\(pendiente\)", re.IGNORECASE)
PENDING_WIKI_ARROW_RE = re.compile(r"\s*→\s*\[\[[^\]]+\]\]\s*\(pendiente\)", re.IGNORECASE)

TopicKind = Literal["tema", "lab", "entregable", "tarea"]


class Topic(BaseModel):
    text: str
    kind: TopicKind
    done: bool | None = None  # only for checkboxes
    pending_wiki: list[str] = []


class Phase(BaseModel):
    number: int
    title: str
    start: date | None
    end: date | None
    topics: list[Topic]
    tasks_done: int
    tasks_total: int


class Roadmap(BaseModel):
    name: str
    note: str
    target_date: date | None
    days_left: int | None
    current: Phase | None
    next: Phase | None
    expected_progress: float | None  # share of the current phase's days already elapsed
    actual_progress: float | None  # share of the current phase's checkboxes done


def _kind(raw: str, is_task: bool) -> TopicKind:
    if is_task:
        return "tarea"
    label = raw.lstrip("*").lower()
    if label.startswith("lab"):
        return "lab"
    if label.startswith("mini-script"):
        return "entregable"
    return "tema"


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _phases(note: Note) -> list[Phase]:
    phase_lines = {}
    for line_no, _level, text in iter_headings(note.body):
        if heading := parse_phase_heading(text):
            phase_lines[line_no] = heading

    topics: dict[int, list[Topic]] = {line: [] for line in phase_lines}
    counts: dict[int, list[int]] = {line: [0, 0] for line in phase_lines}
    for item in parse_list_items(note.body):
        if item.heading_line not in phase_lines:
            continue
        if item.is_task:
            counts[item.heading_line][1] += 1
            counts[item.heading_line][0] += item.done
        if item.parent is None:
            topics[item.heading_line].append(
                Topic(
                    text=clean_text(PENDING_WIKI_ARROW_RE.sub("", item.text)),
                    kind=_kind(item.text, item.is_task),
                    done=item.done if item.is_task else None,
                    pending_wiki=[m.strip() for m in PENDING_WIKI_RE.findall(item.text)],
                )
            )

    return [
        Phase(
            number=h.number,
            title=h.title,
            start=h.start,
            end=h.end,
            topics=topics[line],
            tasks_done=counts[line][0],
            tasks_total=counts[line][1],
        )
        for line, h in sorted(phase_lines.items())
    ]


def parse_roadmap(note: Note, today: date) -> Roadmap:
    phases = _phases(note)
    current = next((p for p in phases if p.start and p.end and p.start <= today <= p.end), None)
    upcoming = next((p for p in phases if p.start and p.start > today), None)

    expected = actual = None
    if current and current.start and current.end:
        total_days = (current.end - current.start).days + 1
        expected = round(((today - current.start).days + 1) / total_days, 2)
        if current.tasks_total:
            actual = round(current.tasks_done / current.tasks_total, 2)

    target = _as_date(note.frontmatter.get("fecha_objetivo"))
    return Roadmap(
        name=project_name(note.title),
        note=note.rel,
        target_date=target,
        days_left=(target - today).days if target else None,
        current=current,
        next=upcoming,
        expected_progress=expected,
        actual_progress=actual,
    )


def collect_study(root: Path, today: date) -> list[Roadmap]:
    return [
        parse_roadmap(note, today)
        for note in iter_notes(root, ROADMAP_FOLDERS)
        if note.is_active and str(note.frontmatter.get("tipo", "")).lower() == "roadmap"
    ]
