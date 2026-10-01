from datetime import date, timedelta

from app.pet import compute_pet, effective_difficulty, mood, streak

TODAY = date(2026, 10, 6)


def days_ago(*offsets: int) -> dict[date, int]:
    return {TODAY - timedelta(days=o): 1 for o in offsets}


def test_streak_counts_back_from_today():
    assert streak(set(days_ago(0, 1, 2, 4)), TODAY) == 3


def test_streak_alive_if_last_activity_was_yesterday():
    assert streak(set(days_ago(1, 2)), TODAY) == 2


def test_streak_broken():
    assert streak(set(days_ago(2, 3)), TODAY) == 0


def test_adaptive_difficulty():
    assert effective_difficulty("normal", idle_days=0, current_streak=1) == "normal"
    assert effective_difficulty("normal", idle_days=3, current_streak=0) == "hardcore"
    assert effective_difficulty("normal", idle_days=None, current_streak=0) == "hardcore"
    assert effective_difficulty("normal", idle_days=0, current_streak=7) == "casual"
    assert effective_difficulty("hardcore", idle_days=5, current_streak=0) == "hardcore"
    assert effective_difficulty("casual", idle_days=0, current_streak=10) == "casual"


def test_active_today_is_full_energy():
    pet = compute_pet("Zebot", days_ago(0, 1), TODAY, "normal")
    assert pet.energy == 100
    assert pet.streak == 2
    assert pet.idle_days == 0


def test_energy_decays_faster_when_idle():
    two_days = compute_pet("Zebot", days_ago(2), TODAY, "normal")
    four_days = compute_pet("Zebot", days_ago(4), TODAY, "normal")
    assert two_days.energy == 70  # normal: 15 per idle day
    assert four_days.effective_difficulty == "hardcore"
    assert four_days.energy == 0  # hardcore: 25 per idle day
    assert four_days.mood == "agotado"


def test_new_pet_is_neutral():
    pet = compute_pet("Zebot", {}, TODAY, "normal")
    assert (pet.energy, pet.streak, pet.level, pet.xp) == (60, 0, 1, 0)


def test_happiness_rewards_active_week_and_study_pace():
    busy = compute_pet("Zebot", days_ago(0, 1, 2, 3, 4), TODAY, "normal", study_pace=0.5)
    behind = compute_pet("Zebot", days_ago(0), TODAY, "normal", study_pace=-0.5)
    assert busy.happiness == 90  # 40 + 8*5 + 20*0.5
    assert behind.happiness == 38  # 40 + 8*1 - 20*0.5
    assert busy.mood == "feliz"


def test_xp_and_level():
    pet = compute_pet("Zebot", {TODAY: 7, TODAY - timedelta(days=1): 5}, TODAY, "normal")
    assert (pet.xp, pet.level) == (120, 2)


def test_mood_rules():
    assert mood(10, 90) == "agotado"
    assert mood(80, 80) == "feliz"
    assert mood(40, 60) == "cansado"
    assert mood(80, 20) == "triste"
    assert mood(80, 50) == "normal"


def test_idle_counts_from_tracking_start_when_no_activity():
    fresh = compute_pet("Zebot", {}, TODAY, "normal", tracking_since=TODAY)
    assert (fresh.idle_days, fresh.energy, fresh.effective_difficulty) == (0, 100, "normal")
    ignored = compute_pet("Zebot", {}, TODAY, "normal", tracking_since=TODAY - timedelta(days=3))
    assert (ignored.idle_days, ignored.effective_difficulty) == (3, "hardcore")
