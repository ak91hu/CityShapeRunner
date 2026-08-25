"""Curated destination art: official-feeling city picks for the composer.

Tourism boards increasingly commission running routes; this catalogue gives a
hand-curated, deterministic answer for the cities GPS Art Wizard knows best.
Every entry maps to an existing route template so the resulting prompt resolves
through the normal fast path. Entries carry a `partner_ready` flag so a future
destination programme can switch individual cities to "official" without a
schema change.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class DestinationArt:
    city: str
    shape_prompt: str
    name: str
    blurb: str
    distance_km: int
    sport: str = "run"
    partner_ready: bool = False


CATALOGUE: tuple[DestinationArt, ...] = (
    DestinationArt(
        city="Budapest",
        shape_prompt="thermal_bath",
        name="Spa city swirl",
        blurb="A thermal-bath silhouette for the city that bathes.",
        distance_km=9,
    ),
    DestinationArt(
        city="Budapest",
        shape_prompt="suspension_bridge",
        name="Bridge walk",
        blurb="A chain-bridge-inspired loop linking the two Danube banks.",
        distance_km=11,
    ),
    DestinationArt(
        city="Szeged",
        shape_prompt="paprika",
        name="Paprika run",
        blurb="Szeged's famous spice, drawn big enough to smell from Strava.",
        distance_km=8,
    ),
    DestinationArt(
        city="Debrecen",
        shape_prompt="flower",
        name="Reform-era bloom",
        blurb="A tidy flower for the Calvinist Rome's tidy squares.",
        distance_km=7,
    ),
    DestinationArt(
        city="Balatonfured",
        shape_prompt="fish",
        name="Balaton fish",
        blurb="Draw the lake's most famous resident on its northern shore.",
        distance_km=8,
        partner_ready=True,
    ),
    DestinationArt(
        city="Siofok",
        shape_prompt="sun",
        name="Sunshine coast",
        blurb="A sun loop on the flat southern shore, best at sunrise.",
        distance_km=10,
        partner_ready=True,
    ),
    DestinationArt(
        city="Keszthely",
        shape_prompt="sailboat",
        name="Sailboat circuit",
        blurb="A sail on land for the lake's western capital.",
        distance_km=8,
        partner_ready=True,
    ),
    DestinationArt(
        city="Vienna",
        shape_prompt="note",
        name="Music city note",
        blurb="A giant music note through the Innere Stadt's grid.",
        distance_km=9,
    ),
    DestinationArt(
        city="Prague",
        shape_prompt="castle",
        name="Castle city loop",
        blurb="A castle silhouette under the Hradcany skyline.",
        distance_km=10,
    ),
    DestinationArt(
        city="London",
        shape_prompt="crown",
        name="Crown jewels loop",
        blurb="A crown for the city that keeps the real ones by the Thames.",
        distance_km=12,
    ),
    DestinationArt(
        city="Rome",
        shape_prompt="helmet",
        name="Gladiator helmet",
        blurb="An arena-era helmet through the Eternal City's streets.",
        distance_km=11,
    ),
)


def _fold(value: str) -> str:
    """Case- and accent-insensitive key so 'Balatonfűred' finds 'Balatonfured'."""

    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def destination_art_for_city(city: str) -> list[dict]:
    """Curated picks for one city, normalised for the composer."""

    wanted = _fold(city)
    if not wanted:
        return []
    matches = [
        entry
        for entry in CATALOGUE
        if _fold(entry.city) == wanted or _fold(entry.city) in wanted
    ]
    return [
        {
            "city": entry.city,
            "shape_prompt": entry.shape_prompt,
            "name": entry.name,
            "blurb": entry.blurb,
            "distance_km": entry.distance_km,
            "sport": entry.sport,
            "partner_ready": entry.partner_ready,
        }
        for entry in matches
    ]
