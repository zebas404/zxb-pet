"""Zebot API: reads the Obsidian vault (read-only) and serves the pet's state."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from . import db
from .briefing import build_context, generate_briefing
from .config import Settings, get_settings
from .pet import PetState, compute_pet
from .vault.study import Roadmap, collect_study
from .vault.tasks import Task, collect_tasks

__version__ = "0.1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Zebot API", version=__version__, description="Backend de la mascota virtual Zebot.")

SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass
class Snapshot:
    today: date
    tasks: list[Task]
    study: list[Roadmap]
    pet: PetState
    recent: list[dict]


def study_pace(study: list[Roadmap]) -> float | None:
    paces = [
        r.actual_progress - r.expected_progress
        for r in study
        if r.actual_progress is not None and r.expected_progress is not None
    ]
    return sum(paces) / len(paces) if paces else None


def take_snapshot(settings: Settings) -> Snapshot:
    """Parse the vault, record newly completed tasks and compute the pet state."""
    if not settings.vault_path.is_dir():
        raise HTTPException(status_code=503, detail=f"Vault no disponible en {settings.vault_path}")
    today = settings.today()
    tasks = collect_tasks(settings.vault_path, today)
    study = collect_study(settings.vault_path, today)
    with db.connect(settings.db_path) as conn:
        db.sync_tasks(conn, tasks, today)
        activity = db.activity_by_day(conn)
        since = db.tracking_since(conn)
        recent = db.recent_activity(conn, today - timedelta(days=7))
    pet = compute_pet(settings.pet_name, activity, today, settings.pet_difficulty, study_pace(study), since)
    return Snapshot(today=today, tasks=tasks, study=study, pet=pet, recent=recent)


# --- Response models ---------------------------------------------------------


class Health(BaseModel):
    status: str
    version: str
    vault_ok: bool
    notes: int
    model: str
    api_key_configured: bool


class TasksResponse(BaseModel):
    date: date
    open: int
    overdue: int
    tasks: list[Task]


class StudyResponse(BaseModel):
    date: date
    roadmaps: list[Roadmap]


class BriefingResponse(BaseModel):
    date: date
    text: str
    source: str  # claude | cache | fallback
    model: str | None
    pet: PetState


# --- Endpoints ---------------------------------------------------------------


@app.get("/health", response_model=Health)
def health(settings: SettingsDep) -> Health:
    vault_ok = settings.vault_path.is_dir()
    notes = sum(1 for _ in settings.vault_path.rglob("*.md")) if vault_ok else 0
    return Health(
        status="ok" if vault_ok else "degraded",
        version=__version__,
        vault_ok=vault_ok,
        notes=notes,
        model=settings.claude_model,
        api_key_configured=bool(settings.anthropic_api_key),
    )


@app.get("/tasks", response_model=TasksResponse)
def tasks(
    settings: SettingsDep,
    include_done: bool = False,
    limit: Annotated[int | None, Query(ge=1, le=500)] = None,
) -> TasksResponse:
    snap = take_snapshot(settings)
    open_tasks = [t for t in snap.tasks if not t.done]
    selected = snap.tasks if include_done else open_tasks
    return TasksResponse(
        date=snap.today,
        open=len(open_tasks),
        overdue=sum(t.overdue for t in open_tasks),
        tasks=selected[:limit] if limit else selected,
    )


@app.get("/study", response_model=StudyResponse)
def study(settings: SettingsDep) -> StudyResponse:
    snap = take_snapshot(settings)
    return StudyResponse(date=snap.today, roadmaps=snap.study)


@app.get("/pet", response_model=PetState)
def pet(settings: SettingsDep) -> PetState:
    return take_snapshot(settings).pet


@app.get("/briefing", response_model=BriefingResponse)
def briefing(settings: SettingsDep, refresh: bool = False) -> BriefingResponse:
    snap = take_snapshot(settings)
    with db.connect(settings.db_path) as conn:
        cached = db.get_briefing(conn, snap.today)
        if cached and not refresh:
            return BriefingResponse(
                date=snap.today, text=cached["content"], source="cache", model=cached["model"], pet=snap.pet
            )
        if cached and refresh and cached["refreshes"] >= settings.briefing_max_refresh_per_day:
            raise HTTPException(status_code=429, detail="Límite de regeneraciones del briefing alcanzado por hoy")

    context = build_context(snap.today, snap.tasks, snap.study, snap.pet, snap.recent)
    text, source = generate_briefing(settings, context, snap.pet.effective_difficulty)
    if source == "claude":  # the fallback is not cached, so the next call retries Claude
        with db.connect(settings.db_path) as conn:
            db.save_briefing(conn, snap.today, text, settings.claude_model, refreshed=bool(cached))
    return BriefingResponse(
        date=snap.today,
        text=text,
        source=source,
        model=settings.claude_model if source == "claude" else None,
        pet=snap.pet,
    )
