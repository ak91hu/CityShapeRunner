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
    country_codes: tuple[str, ...] = ()  # Empty means globally relevant.


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
        country_codes=("HU",),
    ),
    Occasion(
        id="st_patricks_day",
        name="St Patrick's Day",
        shape_prompt="clover",
        detail="Four-leaf clover for the greenest run of the year.",
        month=3,
        day=17,
        country_codes=("IE", "GB", "US"),
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
        country_codes=("AT", "AU", "BE", "CA", "CH", "CZ", "DE", "DK", "EE", "FI", "IT", "NL", "SK", "US"),
    ),
    Occasion(
        id="mothers_day_hu",
        name="Mother's Day",
        shape_prompt="flower",
        detail="Run a flower for the first Sunday of May.",
        nth_weekday=(6, 1),
        month=5,
        country_codes=("HU",),
    ),
    Occasion(
        id="childrens_day",
        name="Children's Day (HU)",
        shape_prompt="balloon",
        detail="A balloon loop for the last Sunday of May.",
        nth_weekday=(6, -1),
        month=5,
        country_codes=("HU",),
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
        country_codes=("HU",),
    ),
    Occasion(
        id="remembrance_october_23",
        name="23 October — Remembrance day (1956)",
        shape_prompt="flame",
        detail="An eternal-flame silhouette for the memorial day.",
        month=10,
        day=23,
        country_codes=("HU",),
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
    Occasion(
        id="us_independence_day",
        name="Independence Day",
        shape_prompt="star",
        detail="A star-shaped route for the Fourth of July.",
        month=7,
        day=4,
        country_codes=("US",),
    ),
    Occasion(
        id="us_labor_day",
        name="Labor Day",
        shape_prompt="medal",
        detail="A medal-shaped route for the first Monday in September.",
        month=9,
        nth_weekday=(0, 1),
        country_codes=("US",),
    ),
    Occasion(
        id="us_thanksgiving",
        name="Thanksgiving",
        shape_prompt="heart",
        detail="Draw a heart-shaped route for a day of gratitude.",
        month=11,
        nth_weekday=(3, 4),
        country_codes=("US",),
    ),
    Occasion(
        id="canada_day",
        name="Canada Day",
        shape_prompt="maple_leaf",
        detail="Draw a maple leaf for Canada Day.",
        month=7,
        day=1,
        country_codes=("CA",),
    ),
    Occasion(
        id="canadian_thanksgiving",
        name="Thanksgiving",
        shape_prompt="maple_leaf",
        detail="A maple-leaf route for Canada's October Thanksgiving.",
        month=10,
        nth_weekday=(0, 2),
        country_codes=("CA",),
    ),
    Occasion(
        id="german_unity_day",
        name="German Unity Day",
        shape_prompt="infinity",
        detail="One continuous line for unity across Germany.",
        month=10,
        day=3,
        country_codes=("DE",),
    ),
    Occasion(
        id="austrian_national_day",
        name="Austrian National Day",
        shape_prompt="mountain",
        detail="A mountain outline for Austria's national holiday.",
        month=10,
        day=26,
        country_codes=("AT",),
    ),
    Occasion(
        id="french_national_day",
        name="Bastille Day",
        shape_prompt="flame",
        detail="A celebratory flame for France's national day.",
        month=7,
        day=14,
        country_codes=("FR",),
    ),
    Occasion(
        id="italian_republic_day",
        name="Republic Day",
        shape_prompt="star",
        detail="A star route for Italy's Festa della Repubblica.",
        month=6,
        day=2,
        country_codes=("IT",),
    ),
    Occasion(
        id="spanish_national_day",
        name="National Day of Spain",
        shape_prompt="sun",
        detail="A sun-shaped route for Spain's national holiday.",
        month=10,
        day=12,
        country_codes=("ES",),
    ),
    Occasion(
        id="portugal_day",
        name="Portugal Day",
        shape_prompt="sailboat",
        detail="A sail-shaped route for Portugal Day.",
        month=6,
        day=10,
        country_codes=("PT",),
    ),
    Occasion(
        id="kings_day_netherlands",
        name="King's Day",
        shape_prompt="crown",
        detail="A crown route for the Netherlands' biggest street celebration.",
        month=4,
        day=27,
        country_codes=("NL",),
    ),
    Occasion(
        id="belgian_national_day",
        name="Belgian National Day",
        shape_prompt="diamond",
        detail="A diamond-shaped route for Belgium's national day.",
        month=7,
        day=21,
        country_codes=("BE",),
    ),
    Occasion(
        id="swiss_national_day",
        name="Swiss National Day",
        shape_prompt="mountain",
        detail="Trace an Alpine silhouette for Switzerland's national day.",
        month=8,
        day=1,
        country_codes=("CH",),
    ),
    Occasion(
        id="norwegian_constitution_day",
        name="Constitution Day",
        shape_prompt="crown",
        detail="A crown-shaped route for Norway's 17 May celebrations.",
        month=5,
        day=17,
        country_codes=("NO",),
    ),
    Occasion(
        id="swedish_national_day",
        name="National Day of Sweden",
        shape_prompt="crown",
        detail="A crown outline for Sweden's national day.",
        month=6,
        day=6,
        country_codes=("SE",),
    ),
    Occasion(
        id="danish_constitution_day",
        name="Constitution Day",
        shape_prompt="crown",
        detail="A crown route for Denmark's Constitution Day.",
        month=6,
        day=5,
        country_codes=("DK",),
    ),
    Occasion(
        id="finnish_independence_day",
        name="Independence Day",
        shape_prompt="snowflake",
        detail="A snowflake route for Finland's Independence Day.",
        month=12,
        day=6,
        country_codes=("FI",),
    ),
    Occasion(
        id="polish_independence_day",
        name="National Independence Day",
        shape_prompt="shield",
        detail="A shield outline for Poland's independence celebration.",
        month=11,
        day=11,
        country_codes=("PL",),
    ),
    Occasion(
        id="czech_independence_day",
        name="Independent Czechoslovak State Day",
        shape_prompt="castle",
        detail="A castle route for the Czech Republic's October holiday.",
        month=10,
        day=28,
        country_codes=("CZ",),
    ),
    Occasion(
        id="slovak_constitution_day",
        name="Constitution Day",
        shape_prompt="shield",
        detail="A shield route for Slovakia's Constitution Day.",
        month=9,
        day=1,
        country_codes=("SK",),
    ),
    Occasion(
        id="irish_st_brigids_day",
        name="St Brigid's Day",
        shape_prompt="cross",
        detail="A cross-shaped route for Ireland's early-February holiday.",
        month=2,
        day=1,
        country_codes=("IE",),
    ),
    Occasion(
        id="uk_bonfire_night",
        name="Bonfire Night",
        shape_prompt="flame",
        detail="A flame-shaped route for the fifth of November.",
        month=11,
        day=5,
        country_codes=("GB",),
    ),
    Occasion(
        id="greek_independence_day",
        name="Greek Independence Day",
        shape_prompt="sun",
        detail="A bright sun route for Greece's national holiday.",
        month=3,
        day=25,
        country_codes=("GR",),
    ),
    Occasion(
        id="romanian_great_union_day",
        name="Great Union Day",
        shape_prompt="infinity",
        detail="A continuous route for Romania's national celebration.",
        month=12,
        day=1,
        country_codes=("RO",),
    ),
    Occasion(
        id="croatian_statehood_day",
        name="Statehood Day",
        shape_prompt="heart",
        detail="A heart route for Croatia's Statehood Day.",
        month=5,
        day=30,
        country_codes=("HR",),
    ),
    Occasion(
        id="slovenian_statehood_day",
        name="Statehood Day",
        shape_prompt="mountain",
        detail="A mountain outline for Slovenia's Statehood Day.",
        month=6,
        day=25,
        country_codes=("SI",),
    ),
    Occasion(
        id="bulgarian_liberation_day",
        name="Liberation Day",
        shape_prompt="flame",
        detail="A flame route for Bulgaria's national holiday.",
        month=3,
        day=3,
        country_codes=("BG",),
    ),
    Occasion(
        id="estonian_independence_day",
        name="Independence Day",
        shape_prompt="star",
        detail="A star route for Estonia's Independence Day.",
        month=2,
        day=24,
        country_codes=("EE",),
    ),
    Occasion(
        id="latvian_independence_day",
        name="Proclamation Day",
        shape_prompt="star",
        detail="A star route for Latvia's proclamation anniversary.",
        month=11,
        day=18,
        country_codes=("LV",),
    ),
    Occasion(
        id="lithuanian_restoration_day",
        name="Restoration of the State Day",
        shape_prompt="star",
        detail="A star route for Lithuania's restoration celebration.",
        month=2,
        day=16,
        country_codes=("LT",),
    ),
)


COUNTRY_NAMES: dict[str, str] = {
    "AL": "Albania",
    "AT": "Austria",
    "AU": "Australia",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CA": "Canada",
    "CH": "Switzerland",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "US": "United States",
    "XK": "Kosovo",
}

TIMEZONE_COUNTRIES: dict[str, str] = {
    "Europe/Amsterdam": "NL",
    "Europe/Athens": "GR",
    "Europe/Berlin": "DE",
    "Europe/Bratislava": "SK",
    "Europe/Brussels": "BE",
    "Europe/Bucharest": "RO",
    "Europe/Budapest": "HU",
    "Europe/Copenhagen": "DK",
    "Europe/Dublin": "IE",
    "Europe/Helsinki": "FI",
    "Europe/Lisbon": "PT",
    "Europe/Ljubljana": "SI",
    "Europe/London": "GB",
    "Europe/Luxembourg": "LU",
    "Europe/Madrid": "ES",
    "Europe/Podgorica": "ME",
    "Europe/Oslo": "NO",
    "Europe/Paris": "FR",
    "Europe/Prague": "CZ",
    "Europe/Riga": "LV",
    "Europe/Rome": "IT",
    "Europe/Sarajevo": "BA",
    "Europe/Skopje": "MK",
    "Europe/Sofia": "BG",
    "Europe/Stockholm": "SE",
    "Europe/Tallinn": "EE",
    "Europe/Tirane": "AL",
    "Europe/Vienna": "AT",
    "Europe/Vilnius": "LT",
    "Europe/Warsaw": "PL",
    "Europe/Zagreb": "HR",
    "Europe/Zurich": "CH",
    "America/Chicago": "US",
    "America/Denver": "US",
    "America/Los_Angeles": "US",
    "America/New_York": "US",
    "America/Toronto": "CA",
    "America/Vancouver": "CA",
    "Australia/Brisbane": "AU",
    "Australia/Melbourne": "AU",
    "Australia/Perth": "AU",
    "Australia/Sydney": "AU",
}


def normalise_country_code(value: str | None) -> str:
    """Return a supported ISO-like country code, or an empty string."""

    code = str(value or "").strip().upper()
    code = {"UK": "GB", "EL": "GR"}.get(code, code)
    return code if len(code) == 2 and code.isascii() and code.isalpha() else ""


def country_from_locale(value: str | None) -> str:
    """Extract a country from a BCP-47 locale such as ``de-DE``."""

    parts = str(value or "").replace("_", "-").split("-")
    for part in reversed(parts[1:]):
        code = normalise_country_code(part)
        if code:
            return code
    language_defaults = {
        "cs": "CZ",
        "da": "DK",
        "de": "DE",
        "el": "GR",
        "en": "GB",
        "es": "ES",
        "et": "EE",
        "fi": "FI",
        "fr": "FR",
        "ga": "IE",
        "hr": "HR",
        "hu": "HU",
        "it": "IT",
        "lt": "LT",
        "lv": "LV",
        "nl": "NL",
        "no": "NO",
        "pl": "PL",
        "pt": "PT",
        "ro": "RO",
        "sk": "SK",
        "sl": "SI",
        "sv": "SE",
    }
    return language_defaults.get(parts[0].lower(), "")


def country_from_timezone(value: str | None) -> str:
    """Map a browser IANA timezone to its most likely country."""

    return TIMEZONE_COUNTRIES.get(str(value or "").strip(), "")


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
    country_code: str | None = "HU",
) -> list[dict]:
    """Global and locally relevant occasions, soonest first."""

    current = today or date.today()
    window_end = current + timedelta(days=days_ahead)
    resolved_country = normalise_country_code(country_code)
    results: list[dict] = []
    for occasion in CATALOGUE:
        if occasion.country_codes and resolved_country not in occasion.country_codes:
            continue
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
                "local": bool(occasion.country_codes),
            }
        )
    results.sort(key=lambda item: item["date"])
    return results
