"""Low-level helpers to read Obsidian notes: frontmatter, headings, list items."""

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
CALLOUT_PREFIX_RE = re.compile(r"^(?:>\s?)+")
TASK_RE = re.compile(r"^(?P<indent>\s*)[-*+] \[(?P<mark>.)\] (?P<text>.*)$")
BULLET_RE = re.compile(r"^(?P<indent>\s*)[-*+] (?P<text>.*)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
MDLINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


@dataclass
class Note:
    path: Path
    rel: str
    frontmatter: dict
    body: str

    @property
    def title(self) -> str:
        return self.path.stem

    @property
    def is_active(self) -> bool:
        return str(self.frontmatter.get("estado", "")).strip().lower() == "vigente"


@dataclass
class ListItem:
    """A bullet or checkbox line with its document context."""

    line_no: int
    indent: int
    text: str
    is_task: bool
    done: bool
    headings: list[str]  # heading texts from H1 down to the closest one
    heading_line: int  # line number of the closest heading (-1 if none)
    parent: str | None  # raw text of the parent bullet, if nested
    children: list["ListItem"] = field(default_factory=list)


def read_note(path: Path, root: Path) -> Note:
    raw = path.read_text(encoding="utf-8", errors="replace")
    fm: dict = {}
    body = raw
    match = FRONTMATTER_RE.match(raw)
    if match:
        try:
            loaded = yaml.safe_load(match.group(1))
            fm = loaded if isinstance(loaded, dict) else {}
        except yaml.YAMLError:
            fm = {}
        body = raw[match.end():]
    return Note(path=path, rel=path.relative_to(root).as_posix(), frontmatter=fm, body=body)


def try_read_note(path: Path, root: Path) -> Note | None:
    """Read a note, or log and skip it if it can't be read (e.g. permissions)."""
    try:
        return read_note(path, root)
    except OSError as e:
        log.warning("Skipping unreadable note %s: %s", path, e)
        return None


def iter_notes(root: Path, folders: list[str]) -> list[Note]:
    notes: list[Note] = []
    for folder in folders:
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.name.startswith("_"):
                continue
            if note := try_read_note(path, root):
                notes.append(note)
    return notes


def clean_text(text: str) -> str:
    """Strip Obsidian/Markdown syntax so the text reads naturally."""
    text = WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)).strip(), text)
    text = MDLINK_RE.sub(r"\1", text)
    text = re.sub(r"(\*\*|__|~~|`)", "", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize(text: str) -> str:
    return clean_text(text).lower().rstrip(".")


def heading_text(heading: str) -> str:
    return clean_text(heading)


def iter_headings(body: str) -> list[tuple[int, int, str]]:
    """Return ``(line_no, level, text)`` for each heading outside code fences."""
    out: list[tuple[int, int, str]] = []
    in_fence = False
    for line_no, line in enumerate(body.splitlines()):
        if FENCE_RE.match(CALLOUT_PREFIX_RE.sub("", line)):
            in_fence = not in_fence
        elif not in_fence and (m := HEADING_RE.match(line)):
            out.append((line_no, len(m.group(1)), heading_text(m.group(2))))
    return out


def parse_list_items(body: str) -> list[ListItem]:
    """Return every bullet/checkbox with its headings and parent bullet.

    Handles callouts (``> - [ ]``), nesting by indentation and skips code fences.
    """
    items: list[ListItem] = []
    headings: dict[int, str] = {}
    heading_line = -1
    stack: list[ListItem] = []  # open bullets, for parent lookup
    in_fence = False

    for line_no, raw_line in enumerate(body.splitlines()):
        if FENCE_RE.match(CALLOUT_PREFIX_RE.sub("", raw_line)):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = HEADING_RE.match(raw_line)
        if heading:
            level = len(heading.group(1))
            headings = {k: v for k, v in headings.items() if k < level}
            headings[level] = heading_text(heading.group(2))
            heading_line = line_no
            stack.clear()
            continue

        line = CALLOUT_PREFIX_RE.sub("", raw_line).expandtabs(4)
        task = TASK_RE.match(line)
        bullet = task or BULLET_RE.match(line)
        if not bullet:
            if line.strip():
                stack.clear()  # a paragraph ends the current list
            continue

        indent = len(bullet.group("indent"))
        while stack and stack[-1].indent >= indent:
            stack.pop()
        parent = stack[-1] if stack else None

        item = ListItem(
            line_no=line_no,
            indent=indent,
            text=bullet.group("text").strip(),
            is_task=bool(task),
            done=bool(task) and task.group("mark").lower() == "x",
            headings=[headings[k] for k in sorted(headings)],
            heading_line=heading_line,
            parent=parent.text if parent else None,
        )
        if parent:
            parent.children.append(item)
        items.append(item)
        stack.append(item)
    return items


# --- Phase headings ----------------------------------------------------------

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
PHASE_RE = re.compile(
    r"^Fase\s+(?P<num>\d+)\s*[—–\-·:]\s*(?P<title>.+?)\s*(?:\((?P<when>[^()]*)\))?\s*$"
)
RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(?:→|->|–|—|a|al|-)\s*(\d{4}-\d{2}-\d{2})")
MONTH_RE = re.compile(r"^([a-záéíóú]+)\s+(\d{4})$", re.IGNORECASE)


@dataclass
class PhaseHeading:
    number: int
    title: str
    start: date | None
    end: date | None

    def contains(self, day: date) -> bool:
        return bool(self.start and self.end and self.start <= day <= self.end)


def parse_phase_heading(text: str) -> PhaseHeading | None:
    """Parse ``Fase 1 — Título (2026-10-05 → 2026-10-18)`` or ``Fase 1 · Título (octubre 2026)``."""
    match = PHASE_RE.match(text.strip())
    if not match:
        return None
    start = end = None
    when = (match.group("when") or "").strip()
    if rng := RANGE_RE.search(when):
        start, end = date.fromisoformat(rng.group(1)), date.fromisoformat(rng.group(2))
    elif (month := MONTH_RE.match(when)) and month.group(1).lower() in MONTHS:
        year, mon = int(month.group(2)), MONTHS[month.group(1).lower()]
        start = date(year, mon, 1)
        end = date(year, mon, calendar.monthrange(year, mon)[1])
    title = match.group("title")
    if match.group("when") is not None and not start:
        title = f"{title} ({when})"  # parentheses that were not a date
    return PhaseHeading(number=int(match.group("num")), title=title, start=start, end=end)
