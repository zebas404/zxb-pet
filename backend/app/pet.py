"""Zebot's Tamagotchi state, derived from activity history and study pace.

Pure functions only, so the rules are easy to test and tune.
"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

from .config import Difficulty

Mood = Literal["feliz", "normal", "cansado", "triste", "agotado"]

LEVELS: list[Difficulty] = ["casual", "normal", "hardcore"]
ENERGY_DECAY_PER_IDLE_DAY = {"casual": 10, "normal": 15, "hardcore": 25}
IDLE_DAYS_TO_HARDEN = 3
STREAK_DAYS_TO_SOFTEN = 7
XP_PER_ACTIVITY = 10
XP_PER_LEVEL = 100


class PetState(BaseModel):
    name: str
    mood: Mood
    energy: int
    happiness: int
    streak: int
    idle_days: int | None
    level: int
    xp: int
    difficulty: Difficulty
    effective_difficulty: Difficulty


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def streak(active_days: set[date], today: date) -> int:
    """Consecutive active days ending today (or yesterday: the streak is still alive today)."""
    day = today if today in active_days else today - timedelta(days=1)
    count = 0
    while day in active_days:
        count += 1
        day -= timedelta(days=1)
    return count


def effective_difficulty(base: Difficulty, idle_days: int | None, current_streak: int) -> Difficulty:
    """Adaptive difficulty: stricter after idle days, softer after a long streak."""
    idx = LEVELS.index(base)
    if idle_days is None or idle_days >= IDLE_DAYS_TO_HARDEN:
        idx += 1
    elif current_streak >= STREAK_DAYS_TO_SOFTEN:
        idx -= 1
    return LEVELS[max(0, min(len(LEVELS) - 1, idx))]


def mood(energy: int, happiness: int) -> Mood:
    if energy <= 15:
        return "agotado"
    if happiness >= 75:
        return "feliz"
    if energy < 50:
        return "cansado"
    if happiness < 35:
        return "triste"
    return "normal"


def compute_pet(
    name: str,
    activity: dict[date, int],
    today: date,
    difficulty: Difficulty,
    study_pace: float | None = None,
    tracking_since: date | None = None,
) -> PetState:
    """Compute the pet state.

    - ``activity``: number of activities per day (task closed, capture…).
    - ``study_pace``: actual minus expected progress of the current study phases (-1…1).
    - ``tracking_since``: first day Zebot watched the vault; idle days count from there
      when there is no activity yet.
    """
    active_days = {d for d, n in activity.items() if n > 0 and d <= today}
    last = max(active_days | ({tracking_since} if tracking_since else set()), default=None)
    idle = (today - last).days if last else None
    current_streak = streak(active_days, today)
    level_now = effective_difficulty(difficulty, idle, current_streak)

    if idle is None:
        energy = 60  # unknown history: neither tired nor full
    else:
        energy = _clamp(100 - ENERGY_DECAY_PER_IDLE_DAY[level_now] * idle)

    week = {today - timedelta(days=i) for i in range(7)}
    active_last_week = len(active_days & week)
    happiness = _clamp(40 + 8 * min(active_last_week, 5) + 20 * max(-1.0, min(1.0, study_pace or 0.0)))

    xp = XP_PER_ACTIVITY * sum(activity.values())
    return PetState(
        name=name,
        mood=mood(energy, happiness),
        energy=energy,
        happiness=happiness,
        streak=current_streak,
        idle_days=idle,
        level=xp // XP_PER_LEVEL + 1,
        xp=xp,
        difficulty=difficulty,
        effective_difficulty=level_now,
    )
