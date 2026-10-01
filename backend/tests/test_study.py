from datetime import date

from app.vault.study import collect_study

from .conftest import TODAY


def roadmap(vault, today=TODAY):
    (only,) = collect_study(vault, today)
    return only


def test_only_roadmap_notes(vault):
    assert [r.name for r in collect_study(vault, TODAY)] == ["Demo Cert"]


def test_current_and_next_phase(vault):
    r = roadmap(vault)
    assert r.current.number == 1
    assert r.current.title == "Cloud Concepts, 24 %"
    assert r.next.number == 2


def test_topics_and_kinds(vault):
    topics = roadmap(vault).current.topics
    assert [(t.kind, t.text) for t in topics] == [
        ("tema", "Beneficios de la nube."),
        ("lab", "Lab: crear un usuario IAM."),
        ("entregable", "Mini-script: sysinfo.py."),
        ("tarea", "Leer el capítulo 1."),
    ]
    assert topics[0].pending_wiki == ["Concepto - Beneficios de la nube AWS"]
    assert topics[3].done is True


def test_progress_counts_nested_checkboxes(vault):
    r = roadmap(vault)
    assert (r.current.tasks_done, r.current.tasks_total) == (1, 2)
    assert r.actual_progress == 0.5
    assert r.expected_progress == round(2 / 14, 2)  # day 2 of 14


def test_target_date_countdown(vault):
    r = roadmap(vault)
    assert r.target_date == date(2026, 12, 5)
    assert r.days_left == 60


def test_between_phases_has_no_current(vault):
    r = roadmap(vault, date(2026, 9, 1))
    assert r.current is None
    assert r.next.number == 0


def test_after_last_phase(vault):
    r = roadmap(vault, date(2027, 1, 1))
    assert r.current is None and r.next is None
