"""Occasion catalog: date-aware drawing suggestions for gifts and holidays.

The catalogue is deterministic. Fixed national days sit next to computable
movable feasts (Easter, Mother's/Father's/Children's Day, first Advent), and
every entry maps to one existing route-template name so the suggested prompt
always resolves through the normal fast path.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm for Western Easter."""

    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """``n``-th ``weekday`` of the month; negative ``n`` counts from the end."""

    days_in_month = calendar.monthrange(year, month)[1]
    if n > 0:
        first_weekday = date(year, month, 1).weekday()
        offset = (weekday - first_weekday) % 7
        day = 1 + offset + (n - 1) * 7
    else:
        last_weekday = date(year, month, days_in_month).weekday()
        offset = (last_weekday - weekday) % 7
        day = days_in_month - offset + (n + 1) * 7
    return date(year, month, day)


@dataclass(frozen=True)
class Occasion:
    id: str
    name: str
    shape_prompt: str
    detail: str
    month: int | None = None
    day: int | None = None
    duration_days: int = 1
    nth_weekday: tuple[int, int] | None = None  # (weekday Mon=0..Sun=6, n)
    movable: str | None = None  # "easter", "advent", or None


CATALOGUE: tuple[Occasion, ...] = (
    Occasion(
        id="valentines_day",
        name="Valentine's Day",
        shape_prompt="heart",
        detail="Draw a heart for someone before the dinner reservation.",
        month=2,
        day=14,
    ),
    Occasion(
        id="national_day_march_15",
        name="15 March — Hungarian national day",
        shape_prompt="bow_tie",
        detail="A cockarde-style loop for the 1848 remembrance.",
        month=3,
        day=15,
    ),
    Occasion(
        id="st_patricks_day",
        name="St Patrick's Day",
        shape_prompt="clover",
        detail="Four-leaf clover for the greenest run of the year.",
        month=3,
        day=17,
    ),
    Occasion(
        id="easter",
        name="Easter",
        shape_prompt="rabbit",
        detail="An Easter-bunny outline while the eggs are hidden.",
        movable="easter",
        duration_days=2,
    ),
    Occasion(
        id="mothers_day",
        name="Mother's Day",
        shape_prompt="flower",
        detail="Run a flower and bring breakfast at the finish.",
        nth_weekday=(6, 2),
        month=5,
    ),
    Occasion(
        id="childrens_day",
        name="Children's Day (HU)",
        shape_prompt="balloon",
        detail="A balloon loop for the last Sunday of May.",
        nth_weekday=(6, -1),
        month=5,
    ),
    Occasion(
        id="fathers_day",
        name="Father's Day",
        shape_prompt="mug",
        detail="A coffee-mug circuit to pair with the grilling.",
        nth_weekday=(6, 3),
        month=6,
    ),
    Occasion(
        id="international_cat_day",
        name="International Cat Day",
        shape_prompt="cat",
        detail="Draw the household's real boss on the city map.",
        month=8,
        day=8,
    ),
    Occasion(
        id="state_foundation_day",
        name="20 August — State Foundation & New Bread Day",
        shape_prompt="wheat",
        detail="A wheat stalk for the new-bread and state-foundation holiday.",
        month=8,
        day=20,
    ),
    Occasion(
        id="remembrance_october_23",
        name="23 October — Remembrance day (1956)",
        shape_prompt="flame",
        detail="An eternal-flame silhouette for the memorial day.",
        month=10,
        day=23,
    ),
    Occasion(
        id="halloween",
        name="Halloween",
        shape_prompt="ghost",
        detail="A friendly ghost that only exists on Strava.",
        month=10,
        day=31,
    ),
    Occasion(
        id="first_advent",
        name="First Advent",
        shape_prompt="candle",
        detail="Light the first candle with your feet.",
        movable="advent",
    ),
    Occasion(
        id="christmas",
        name="Christmas",
        shape_prompt="pine_tree",
        detail="A tree-shaped loop to earn the evening dinner.",
        month=12,
        day=24,
        duration_days=3,
    ),
    Occasion(
        id="new_years_eve",
        name="New Year's Eve",
        shape_prompt="star",
        detail="Close the year with a star before midnight.",
        month=12,
        day=31,
        duration_days=2,
    ),
)


def occasion_date(occasion: Occasion, year: int) -> date:
    """Resolve one occurrence of an occasion in a given year."""

    if occasion.movable == "easter":
        return _easter_sunday(year)
    if occasion.movable == "advent":
        christmas = date(year, 12, 25)
        # The fourth Advent Sunday is strictly before Christmas Day. When
        # Christmas itself is Sunday, the previous Sunday is 18 December.
        last_advent = christmas - timedelta(days=christmas.weekday() + 1)
        return last_advent - timedelta(days=21)
    if occasion.nth_weekday is not None:
        weekday, position = occasion.nth_weekday
        return _nth_weekday(year, occasion.month or 1, weekday, position)
    return date(year, occasion.month or 1, occasion.day or 1)


def _next_occurrence_on_or_after(occasion: Occasion, today: date) -> date:
    candidate = occasion_date(occasion, today.year)
    # A multi-day occasion that started near the end of last year can still be
    # ongoing today; prefer that live occurrence over the next year's date.
    if candidate > today:
        previous = occasion_date(occasion, today.year - 1)
        if previous + timedelta(days=occasion.duration_days - 1) >= today:
            return previous
    if candidate + timedelta(days=occasion.duration_days - 1) < today:
        candidate = occasion_date(occasion, today.year + 1)
    return candidate


def upcoming_occasions(
    *,
    today: date | None = None,
    days_ahead: int = 60,
) -> list[dict]:
    """Occasions starting within ``days_ahead``, soonest first."""

    current = today or date.today()
    window_end = current + timedelta(days=days_ahead)
    results: list[dict] = []
    for occasion in CATALOGUE:
        starts = _next_occurrence_on_or_after(occasion, current)
        if starts > window_end:
            continue
        # A multi-day occasion that already started stays listed as "today"
        # for its whole duration instead of reporting a negative countdown.
        days_until = max(0, (starts - current).days)
        results.append(
            {
                "id": occasion.id,
                "name": occasion.name,
                "date": starts.isoformat(),
                "days_until": days_until,
                "shape_prompt": occasion.shape_prompt,
                "detail": occasion.detail,
                "duration_days": occasion.duration_days,
            }
        )
    results.sort(key=lambda item: item["date"])
    return results
