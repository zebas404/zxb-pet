"""Parse open/closed tasks (``- [ ]`` / ``- [x]``) from the vault."""

import hashlib
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from .markdown import Note, clean_text, iter_notes, normalize, parse_list_items, parse_phase_heading, try_read_note

TASK_FOLDERS = ["01-Proyectos", "02-Areas"]
PENDING_NOTE = "99-Sistema/pendientes.md"
PENDING_SECTION = "dudas abiertas"
NEXT_STEPS_SECTION = "próximos pasos"
IGNORED_NOTE_TYPES = {"runbook"}
TITLE_PREFIXES =("Proyecto - ", "Roadmap - ", "Area - ", "Área - ")

PRIORITY_NEXT_STEPS = 1
PRIORITY_CURRENT_PHASE = 2
PRIORITY_OTHER = 3


class Task(BaseModel):
    id: str
    text: str
    done: bool
    project: str
    section: str | None
    parent: str | None
    priority: int
    overdue: bool  # open task in a dated phase that already ended
    notes: list[str]


def project_name(title: str) -> str:
    for prefix in TITLE_PREFIXES:
        if title.startswith(prefix):
            return title[len(prefix):]
    return title


def task_id(text: str) -> str:
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()[:12]


def _priority(headings: list[str], today: date) -> tuple[int, bool]:
    """Return ``(priority, phase_ended)`` for a task under these headings."""
    phases = [p for h in headings if (p := parse_phase_heading(h))]
    ended = any(p.end and p.end < today for p in phases)
    if any(h.lower() == NEXT_STEPS_SECTION for h in headings):
        return PRIORITY_NEXT_STEPS, ended
    if any(p.contains(today) for p in phases):
        return PRIORITY_CURRENT_PHASE, ended
    return PRIORITY_OTHER, ended


def _tasks_from_note(note: Note, today: date, project: str, only_section: str | None = None) -> list[Task]:
    tasks = []
    for item in parse_list_items(note.body):
        if not item.is_task:
            continue
        if only_section and not any(h.lower() == only_section for h in item.headings):
            continue
        # The H1 is the note title; the section is the closest heading below it.
        section = item.headings[-1] if len(item.headings) > 1 else None
        parent = clean_text(item.parent).rstrip(":").strip() if item.parent else None
        priority, phase_ended = (PRIORITY_NEXT_STEPS, False) if only_section else _priority(item.headings, today)
        tasks.append(
            Task(
                id=task_id(item.text),
                text=clean_text(item.text),
                done=item.done,
                project=project,
                section=section,
                parent=parent or None,
                priority=priority,
                overdue=phase_ended and not item.done,
                notes=[note.rel],
            )
        )
    return tasks


def _dedupe(tasks: list[Task]) -> list[Task]:
    """Merge tasks with the same normalized text (e.g. repeated in a project and its area)."""
    merged: dict[str, Task] = {}
    for task in tasks:
        current = merged.get(task.id)
        if current is None:
            merged[task.id] = task
            continue
        keep = current if current.priority <= task.priority else task
        keep = keep.model_copy(
            update={
                "done": current.done or task.done,
                "overdue": (current.overdue or task.overdue) and not (current.done or task.done),
                "notes": sorted(set(current.notes) | set(task.notes)),
            }
        )
        merged[task.id] = keep
    return list(merged.values())


def collect_tasks(root: Path, today: date) -> list[Task]:
    """All tasks (open and done) from active notes, deduplicated and sorted by priority."""
    tasks: list[Task] = []
    for note in iter_notes(root, TASK_FOLDERS):
        # Runbook checkboxes are validation checklists, not tasks.
        if note.is_active and str(note.frontmatter.get("tipo", "")).lower() not in IGNORED_NOTE_TYPES:
            tasks.extend(_tasks_from_note(note, today, project_name(note.title)))

    pending = root / PENDING_NOTE
    if pending.is_file() and (note := try_read_note(pending, root)):
        tasks.extend(_tasks_from_note(note, today, "Pendientes del agente", only_section=PENDING_SECTION))

    tasks = _dedupe(tasks)
    return sorted(tasks, key=lambda t: (t.done, t.priority, t.project))
