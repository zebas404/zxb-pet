from datetime import date

import pytest

from app.vault.markdown import clean_text, parse_list_items, parse_phase_heading


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ver [[Area - Marca personal]].", "Ver Area - Marca personal."),
        ("Ver [[Area - Marca personal|el área]].", "Ver el área."),
        ("Ver [[Nota#Sección]].", "Ver Nota."),
        ("**Lab:** crear `sysinfo.py`", "Lab: crear sysinfo.py"),
        ("Leer *Show Your Work!* hoy", "Leer Show Your Work! hoy"),
        ("Portal [AWS](https://aws.amazon.com)", "Portal AWS"),
        ("~60 % del círculo", "~60 % del círculo"),
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


def test_phase_heading_with_date_range():
    phase = parse_phase_heading("Fase 1 — Cloud Concepts, 24 % (2026-10-05 → 2026-10-18)")
    assert phase.number == 1
    assert phase.title == "Cloud Concepts, 24 %"
    assert (phase.start, phase.end) == (date(2026, 10, 5), date(2026, 10, 18))
    assert phase.contains(date(2026, 10, 18))
    assert not phase.contains(date(2026, 10, 19))


def test_phase_heading_with_month():
    phase = parse_phase_heading("Fase 3 · Identidad visual (diciembre 2026)")
    assert (phase.start, phase.end) == (date(2026, 12, 1), date(2026, 12, 31))


def test_phase_heading_without_dates():
    phase = parse_phase_heading("Fase 3 · Infraestructura en AWS (Zeb, guiado)")
    assert phase.start is None
    assert phase.title == "Infraestructura en AWS (Zeb, guiado)"


def test_not_a_phase():
    assert parse_phase_heading("Próximos pasos") is None


def test_list_items_nesting_callouts_and_fences():
    body = "\n".join(
        [
            "## Sección",
            "- **Definir:**",
            "  - [ ] hija",
            "> - [x] en callout",
            "```",
            "- [ ] en código",
            "```",
        ]
    )
    items = parse_list_items(body)
    assert [(i.text, i.is_task, i.done, i.parent) for i in items] == [
        ("**Definir:**", False, False, None),
        ("hija", True, False, "**Definir:**"),
        ("en callout", True, True, None),
    ]
    assert items[1].headings == ["Sección"]
