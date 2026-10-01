from app.vault.tasks import PRIORITY_CURRENT_PHASE, PRIORITY_NEXT_STEPS, PRIORITY_OTHER, collect_tasks

from .conftest import TODAY


def by_text(tasks):
    return {t.text: t for t in tasks}


def test_only_active_notes_in_projects_and_areas(vault):
    texts = set(by_text(collect_tasks(vault, TODAY)))
    assert "Esto no debe aparecer." not in texts  # estado: obsoleto
    assert "Tampoco esto." not in texts  # _LEEME.md
    assert "Checklist de validación, no tarea." not in texts  # 03-Wiki
    assert "esto es código, no una tarea" not in texts  # code fence


def test_callout_task_is_parsed(vault):
    assert "Tarea dentro de un callout." in by_text(collect_tasks(vault, TODAY))


def test_text_is_cleaned_and_parent_kept(vault):
    task = by_text(collect_tasks(vault, TODAY))["Pilares de contenido (ver el área)."]
    assert task.parent == "Definir"
    assert task.project == "Demo"
    assert task.section == "Fase 1 · Estrategia (septiembre 2026)"


def test_priorities(vault):
    tasks = by_text(collect_tasks(vault, TODAY))
    assert tasks["Tomar la foto de perfil nueva."].priority == PRIORITY_NEXT_STEPS
    assert tasks["Bio corta y bio larga."].priority == PRIORITY_CURRENT_PHASE  # octubre 2026
    assert tasks["Pilares de contenido (ver el área)."].priority == PRIORITY_OTHER


def test_overdue_only_for_open_tasks_in_ended_phases(vault):
    tasks = by_text(collect_tasks(vault, TODAY))
    assert tasks["Pilares de contenido (ver el área)."].overdue  # septiembre ended
    assert tasks["Leer la exam guide."].overdue  # Fase 0 ended 2026-10-04
    assert not tasks["Curso terminado."].overdue
    assert not tasks["Bio corta y bio larga."].overdue


def test_duplicates_are_merged(vault):
    matches = [t for t in collect_tasks(vault, TODAY) if t.text == "Tomar la foto de perfil nueva."]
    assert len(matches) == 1
    assert matches[0].notes == ["01-Proyectos/Proyecto - Demo.md", "02-Areas/Area - Demo.md"]
    assert matches[0].project == "Demo"  # the next-steps copy wins


def test_pending_doubts_only_from_open_section(vault):
    pending = [t for t in collect_tasks(vault, TODAY) if t.project == "Pendientes del agente"]
    assert [t.text for t in pending] == ["2026-09-30 · nota.md · ¿Fuente o wiki?"]
    assert pending[0].priority == PRIORITY_NEXT_STEPS


def test_sorted_open_first_then_priority(vault):
    tasks = collect_tasks(vault, TODAY)
    keys = [(t.done, t.priority) for t in tasks]
    assert keys == sorted(keys)


def test_ids_are_stable(vault):
    first = {t.id for t in collect_tasks(vault, TODAY)}
    assert first == {t.id for t in collect_tasks(vault, TODAY)}
