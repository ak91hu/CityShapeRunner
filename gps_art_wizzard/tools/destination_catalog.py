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
    country_code: str = "HU"
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
        country_code="AT",
    ),
    DestinationArt(
        city="Prague",
        shape_prompt="castle",
        name="Castle city loop",
        blurb="A castle silhouette under the Hradcany skyline.",
        distance_km=10,
        country_code="CZ",
    ),
    DestinationArt(
        city="London",
        shape_prompt="crown",
        name="Crown jewels loop",
        blurb="A crown for the city that keeps the real ones by the Thames.",
        distance_km=12,
        country_code="GB",
    ),
    DestinationArt(
        city="Rome",
        shape_prompt="helmet",
        name="Gladiator helmet",
        blurb="An arena-era helmet through the Eternal City's streets.",
        distance_km=11,
        country_code="IT",
    ),
    DestinationArt(
        city="Budapest",
        shape_prompt="puzzle_cube",
        name="Rubik city grid",
        blurb="A puzzle-cube outline for the city where the icon was invented.",
        distance_km=12,
        sport="bike",
    ),
    DestinationArt(
        city="Pécs",
        shape_prompt="pomegranate",
        name="Mediterranean pomegranate",
        blurb="A sun-warmed pomegranate through Pecs's southern streets.",
        distance_km=9,
    ),
    DestinationArt(
        city="Vienna",
        shape_prompt="crown",
        name="Imperial crown",
        blurb="A compact crown inspired by Vienna's imperial centre.",
        distance_km=11,
        country_code="AT",
    ),
    DestinationArt(
        city="Prague",
        shape_prompt="chess_pawn",
        name="Bohemian chess move",
        blurb="A chess pawn fitted to Prague's varied street pattern.",
        distance_km=9,
        country_code="CZ",
    ),
    DestinationArt(
        city="London",
        shape_prompt="umbrella",
        name="London umbrella",
        blurb="A weather-ready umbrella beside the Thames.",
        distance_km=10,
        country_code="GB",
    ),
    DestinationArt(
        city="Rome",
        shape_prompt="pizza_slice",
        name="Roman slice",
        blurb="A playful pizza-slice circuit in the Eternal City.",
        distance_km=9,
        country_code="IT",
    ),
    DestinationArt(
        city="Paris",
        shape_prompt="heart",
        name="City of love",
        blurb="A heart-shaped run for Paris's broad boulevards.",
        distance_km=9,
        country_code="FR",
    ),
    DestinationArt(
        city="Paris",
        shape_prompt="camera",
        name="Postcard frame",
        blurb="Frame a piece of Paris as one giant street photograph.",
        distance_km=12,
        country_code="FR",
        sport="bike",
    ),
    DestinationArt(
        city="Berlin",
        shape_prompt="bear",
        name="Berlin bear",
        blurb="The city's heraldic bear, drawn across its generous grid.",
        distance_km=12,
        country_code="DE",
    ),
    DestinationArt(
        city="Berlin",
        shape_prompt="infinity",
        name="United line",
        blurb="One uninterrupted line across the once-divided city.",
        distance_km=18,
        country_code="DE",
        sport="bike",
    ),
    DestinationArt(
        city="Madrid",
        shape_prompt="sun",
        name="Madrid sun",
        blurb="A bright radial route for the heart of Spain.",
        distance_km=10,
        country_code="ES",
    ),
    DestinationArt(
        city="Madrid",
        shape_prompt="bear",
        name="Bear of Madrid",
        blurb="A nod to the bear at Puerta del Sol.",
        distance_km=13,
        country_code="ES",
    ),
    DestinationArt(
        city="Barcelona",
        shape_prompt="wave",
        name="Mediterranean wave",
        blurb="A rolling wave along Barcelona's coastal grid.",
        distance_km=11,
        country_code="ES",
    ),
    DestinationArt(
        city="Barcelona",
        shape_prompt="sailboat",
        name="Port sail",
        blurb="A sailboat circuit for the city's seafront streets.",
        distance_km=16,
        country_code="ES",
        sport="bike",
    ),
    DestinationArt(
        city="Amsterdam",
        shape_prompt="windmill",
        name="Canal windmill",
        blurb="A windmill silhouette around Amsterdam's canal pattern.",
        distance_km=12,
        country_code="NL",
    ),
    DestinationArt(
        city="Amsterdam",
        shape_prompt="tulip",
        name="City tulip",
        blurb="A tulip route made for a flat, bike-friendly city.",
        distance_km=18,
        country_code="NL",
        sport="bike",
    ),
    DestinationArt(
        city="Brussels",
        shape_prompt="diamond",
        name="European diamond",
        blurb="A crisp diamond loop through the Belgian capital.",
        distance_km=8,
        country_code="BE",
    ),
    DestinationArt(
        city="Copenhagen",
        shape_prompt="swan",
        name="Harbour swan",
        blurb="A clean swan silhouette for Copenhagen's calm waterfront.",
        distance_km=11,
        country_code="DK",
    ),
    DestinationArt(
        city="Stockholm",
        shape_prompt="crown",
        name="Three-crown loop",
        blurb="A royal crown among Stockholm's islands.",
        distance_km=12,
        country_code="SE",
    ),
    DestinationArt(
        city="Stockholm",
        shape_prompt="snowflake",
        name="Nordic snowflake",
        blurb="A winter-ready snowflake on Stockholm's street network.",
        distance_km=16,
        country_code="SE",
        sport="bike",
    ),
    DestinationArt(
        city="Oslo",
        shape_prompt="mountain",
        name="Fjord mountain",
        blurb="A mountain profile between Oslo's city and fjord.",
        distance_km=11,
        country_code="NO",
    ),
    DestinationArt(
        city="Helsinki",
        shape_prompt="snowflake",
        name="Baltic snowflake",
        blurb="A geometric snowflake for Helsinki's coastal grid.",
        distance_km=12,
        country_code="FI",
    ),
    DestinationArt(
        city="Helsinki",
        shape_prompt="sailboat",
        name="Archipelago sail",
        blurb="A sailboat route inspired by Helsinki's island horizon.",
        distance_km=18,
        country_code="FI",
        sport="bike",
    ),
    DestinationArt(
        city="Warsaw",
        shape_prompt="shield",
        name="Warsaw shield",
        blurb="A resilient shield across the Polish capital's broad streets.",
        distance_km=11,
        country_code="PL",
    ),
    DestinationArt(
        city="Warsaw",
        shape_prompt="hedgehog",
        name="Vistula hedgehog",
        blurb="A friendly, detailed silhouette suited to Warsaw's grid.",
        distance_km=14,
        country_code="PL",
    ),
    DestinationArt(
        city="Kraków",
        shape_prompt="dragon",
        name="Wawel dragon",
        blurb="The Wawel legend turned into a long city ride.",
        distance_km=22,
        country_code="PL",
        sport="bike",
    ),
    DestinationArt(
        city="Kraków",
        shape_prompt="castle",
        name="Royal castle loop",
        blurb="A compact castle silhouette near Krakow's historic grid.",
        distance_km=10,
        country_code="PL",
    ),
    DestinationArt(
        city="Bratislava",
        shape_prompt="castle",
        name="Danube castle",
        blurb="A castle outline above the Danube-side street network.",
        distance_km=9,
        country_code="SK",
    ),
    DestinationArt(
        city="Ljubljana",
        shape_prompt="dragon",
        name="Ljubljana dragon",
        blurb="The city's green dragon translated into a bike route.",
        distance_km=20,
        country_code="SI",
        sport="bike",
    ),
    DestinationArt(
        city="Zagreb",
        shape_prompt="heart",
        name="Licitar heart",
        blurb="A heart inspired by Croatia's bright licitar tradition.",
        distance_km=10,
        country_code="HR",
    ),
    DestinationArt(
        city="Bucharest",
        shape_prompt="crown",
        name="Royal Bucharest",
        blurb="A crown route through the capital's monumental avenues.",
        distance_km=12,
        country_code="RO",
    ),
    DestinationArt(
        city="Sofia",
        shape_prompt="mountain",
        name="Vitosha outline",
        blurb="A mountain profile inspired by Sofia's southern horizon.",
        distance_km=11,
        country_code="BG",
    ),
    DestinationArt(
        city="Athens",
        shape_prompt="helmet",
        name="Athenian helmet",
        blurb="A classical helmet fitted to the modern city's streets.",
        distance_km=12,
        country_code="GR",
    ),
    DestinationArt(
        city="Athens",
        shape_prompt="sun",
        name="Attic sun",
        blurb="A bright sunburst for an early Athens run.",
        distance_km=9,
        country_code="GR",
    ),
    DestinationArt(
        city="Dublin",
        shape_prompt="clover",
        name="Dublin clover",
        blurb="A clover outline for the streets of the Irish capital.",
        distance_km=10,
        country_code="IE",
    ),
    DestinationArt(
        city="Dublin",
        shape_prompt="mug",
        name="Cosy city mug",
        blurb="A warm mug silhouette for a cool Dublin morning.",
        distance_km=9,
        country_code="IE",
    ),
    DestinationArt(
        city="Munich",
        shape_prompt="pretzel",
        name="Munich pretzel",
        blurb="A continuous pretzel through Munich's orderly streets.",
        distance_km=12,
        country_code="DE",
    ),
    DestinationArt(
        city="Milan",
        shape_prompt="diamond",
        name="Design district diamond",
        blurb="A sharp geometric route for Italy's design capital.",
        distance_km=10,
        country_code="IT",
    ),
    DestinationArt(
        city="Lisbon",
        shape_prompt="sailboat",
        name="Tagus sail",
        blurb="A sail-shaped route where Lisbon meets the Tagus.",
        distance_km=11,
        country_code="PT",
    ),
    DestinationArt(
        city="Lisbon",
        shape_prompt="train",
        name="Hill tram",
        blurb="A tram-inspired line for Lisbon's famous slopes.",
        distance_km=9,
        country_code="PT",
    ),
    DestinationArt(
        city="Porto",
        shape_prompt="wine_glass",
        name="Port wine glass",
        blurb="A wine-glass outline beside the Douro.",
        distance_km=10,
        country_code="PT",
    ),
    DestinationArt(
        city="Porto",
        shape_prompt="lighthouse",
        name="Atlantic lighthouse",
        blurb="A lighthouse route pointing toward the ocean.",
        distance_km=12,
        country_code="PT",
    ),
    DestinationArt(
        city="Zurich",
        shape_prompt="mountain",
        name="Alpine horizon",
        blurb="An Alpine silhouette beside Zurich's lake grid.",
        distance_km=10,
        country_code="CH",
    ),
    DestinationArt(
        city="Tallinn",
        shape_prompt="castle",
        name="Old Town towers",
        blurb="A castle silhouette inspired by Tallinn's medieval skyline.",
        distance_km=9,
        country_code="EE",
    ),
    DestinationArt(
        city="Riga",
        shape_prompt="leaf",
        name="Art Nouveau leaf",
        blurb="An organic leaf line for Riga's decorative streets.",
        distance_km=9,
        country_code="LV",
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
            "country_code": entry.country_code,
            "sport": entry.sport,
            "partner_ready": entry.partner_ready,
        }
        for entry in matches
    ]
