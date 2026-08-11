"""Additional offline European city centres and routing profiles.

The catalogue stores route-search centres rather than claiming authoritative
administrative boundaries.  Compact bounding boxes are derived in
``geocoder.py`` so placement stays in the urban street fabric.  The profile
tags generate consistent recommendation inputs for grid order, connectivity,
barriers, and terrain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class EuropeanCitySeed:
    lat: float
    lon: float
    profile: str
    scale: str = "medium"


# Coordinates are city-centre reference points rounded to four decimals. City
# coverage follows Eurostat's city/FUA framework as a regional sampling guide;
# these product search centres are not Eurostat boundary data:
# https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/cities-functional-urban-areas
# Existing European and Hungarian cities intentionally do not appear here.
ADDITIONAL_EUROPEAN_CITIES: Final[dict[str, EuropeanCitySeed]] = {
    # United Kingdom and Ireland
    "Birmingham": EuropeanCitySeed(52.4862, -1.8904, "grid"),
    "Manchester": EuropeanCitySeed(53.4808, -2.2426, "grid", "large"),
    "Liverpool": EuropeanCitySeed(53.4084, -2.9916, "coastal_grid"),
    "Leeds": EuropeanCitySeed(53.8008, -1.5491, "mixed"),
    "Glasgow": EuropeanCitySeed(55.8642, -4.2518, "river_grid", "large"),
    "Edinburgh": EuropeanCitySeed(55.9533, -3.1883, "hilly_grid"),
    "Bristol": EuropeanCitySeed(51.4545, -2.5879, "hilly_river"),
    "Belfast": EuropeanCitySeed(54.5973, -5.9301, "coastal_grid"),
    "Cork": EuropeanCitySeed(51.8985, -8.4756, "hilly_river", "compact"),
    # France
    "Marseille": EuropeanCitySeed(43.2965, 5.3698, "coastal_hilly", "large"),
    "Lyon": EuropeanCitySeed(45.7640, 4.8357, "river_grid", "large"),
    "Toulouse": EuropeanCitySeed(43.6047, 1.4442, "river_grid"),
    "Nice": EuropeanCitySeed(43.7102, 7.2620, "coastal_hilly"),
    "Nantes": EuropeanCitySeed(47.2184, -1.5536, "river_grid"),
    "Strasbourg": EuropeanCitySeed(48.5734, 7.7521, "canal_grid"),
    "Bordeaux": EuropeanCitySeed(44.8378, -0.5792, "river_grid"),
    "Lille": EuropeanCitySeed(50.6292, 3.0573, "grid"),
    "Montpellier": EuropeanCitySeed(43.6108, 3.8767, "mixed"),
    "Grenoble": EuropeanCitySeed(45.1885, 5.7245, "mountain_grid", "compact"),
    # Germany
    "Hamburg": EuropeanCitySeed(53.5511, 9.9937, "canal_grid", "large"),
    "Cologne": EuropeanCitySeed(50.9375, 6.9603, "river_grid", "large"),
    "Frankfurt": EuropeanCitySeed(50.1109, 8.6821, "river_grid"),
    "Stuttgart": EuropeanCitySeed(48.7758, 9.1829, "hilly_grid"),
    "Düsseldorf": EuropeanCitySeed(51.2277, 6.7735, "river_grid"),
    "Leipzig": EuropeanCitySeed(51.3397, 12.3731, "grid"),
    "Dresden": EuropeanCitySeed(51.0504, 13.7373, "river_grid"),
    "Nuremberg": EuropeanCitySeed(49.4521, 11.0767, "mixed"),
    "Hanover": EuropeanCitySeed(52.3759, 9.7320, "grid"),
    "Bremen": EuropeanCitySeed(53.0793, 8.8017, "river_grid"),
    # Spain
    "Valencia": EuropeanCitySeed(39.4699, -0.3763, "coastal_grid", "large"),
    "Seville": EuropeanCitySeed(37.3891, -5.9845, "river_grid", "large"),
    "Zaragoza": EuropeanCitySeed(41.6488, -0.8891, "river_grid"),
    "Málaga": EuropeanCitySeed(36.7213, -4.4214, "coastal_hilly"),
    "Bilbao": EuropeanCitySeed(43.2630, -2.9350, "hilly_river"),
    "Alicante": EuropeanCitySeed(38.3452, -0.4810, "coastal_grid"),
    "Granada": EuropeanCitySeed(37.1773, -3.5986, "hilly_grid"),
    "Valladolid": EuropeanCitySeed(41.6523, -4.7245, "grid"),
    "Vigo": EuropeanCitySeed(42.2406, -8.7207, "coastal_hilly"),
    "A Coruña": EuropeanCitySeed(43.3623, -8.4115, "coastal_grid", "compact"),
    # Italy
    "Naples": EuropeanCitySeed(40.8518, 14.2681, "coastal_mixed", "large"),
    "Turin": EuropeanCitySeed(45.0703, 7.6869, "grid", "large"),
    "Bologna": EuropeanCitySeed(44.4949, 11.3426, "radial_grid"),
    "Florence": EuropeanCitySeed(43.7696, 11.2558, "river_mixed"),
    "Genoa": EuropeanCitySeed(44.4056, 8.9463, "coastal_hilly"),
    "Palermo": EuropeanCitySeed(38.1157, 13.3615, "coastal_grid", "large"),
    "Bari": EuropeanCitySeed(41.1171, 16.8719, "coastal_grid"),
    "Verona": EuropeanCitySeed(45.4384, 10.9916, "river_mixed"),
    "Padua": EuropeanCitySeed(45.4064, 11.8768, "canal_grid"),
    "Trieste": EuropeanCitySeed(45.6495, 13.7768, "coastal_hilly"),
    # Poland
    "Łódź": EuropeanCitySeed(51.7592, 19.4560, "grid", "large"),
    "Wrocław": EuropeanCitySeed(51.1079, 17.0385, "river_grid", "large"),
    "Poznań": EuropeanCitySeed(52.4064, 16.9252, "grid"),
    "Gdańsk": EuropeanCitySeed(54.3520, 18.6466, "coastal_grid"),
    "Szczecin": EuropeanCitySeed(53.4285, 14.5528, "river_mixed"),
    "Lublin": EuropeanCitySeed(51.2465, 22.5684, "hilly_grid"),
    "Katowice": EuropeanCitySeed(50.2649, 19.0238, "grid"),
    "Bydgoszcz": EuropeanCitySeed(53.1235, 18.0084, "river_grid"),
    # Nordic cities
    "Gothenburg": EuropeanCitySeed(57.7089, 11.9746, "coastal_grid", "large"),
    "Malmö": EuropeanCitySeed(55.6050, 13.0038, "grid"),
    "Uppsala": EuropeanCitySeed(59.8586, 17.6389, "grid", "compact"),
    "Bergen": EuropeanCitySeed(60.3913, 5.3221, "coastal_hilly"),
    "Trondheim": EuropeanCitySeed(63.4305, 10.3951, "coastal_hilly"),
    "Stavanger": EuropeanCitySeed(58.9700, 5.7331, "coastal_mixed"),
    "Aarhus": EuropeanCitySeed(56.1629, 10.2039, "coastal_grid"),
    "Odense": EuropeanCitySeed(55.4038, 10.4024, "grid"),
    "Tampere": EuropeanCitySeed(61.4978, 23.7610, "lake_grid"),
    "Turku": EuropeanCitySeed(60.4518, 22.2666, "coastal_river"),
    "Oulu": EuropeanCitySeed(65.0121, 25.4651, "coastal_grid"),
    # Benelux and Luxembourg
    "Rotterdam": EuropeanCitySeed(51.9244, 4.4777, "river_grid", "large"),
    "The Hague": EuropeanCitySeed(52.0705, 4.3007, "coastal_grid"),
    "Utrecht": EuropeanCitySeed(52.0907, 5.1214, "canal_grid"),
    "Eindhoven": EuropeanCitySeed(51.4416, 5.4697, "grid"),
    "Antwerp": EuropeanCitySeed(51.2194, 4.4025, "river_grid", "large"),
    "Ghent": EuropeanCitySeed(51.0543, 3.7174, "canal_grid"),
    "Liège": EuropeanCitySeed(50.6326, 5.5797, "hilly_river"),
    "Luxembourg": EuropeanCitySeed(49.6116, 6.1319, "hilly_mixed", "compact"),
    # Austria and Switzerland
    "Salzburg": EuropeanCitySeed(47.8095, 13.0550, "mountain_river"),
    "Graz": EuropeanCitySeed(47.0707, 15.4395, "river_grid"),
    "Innsbruck": EuropeanCitySeed(47.2692, 11.4041, "mountain_grid", "compact"),
    "Linz": EuropeanCitySeed(48.3069, 14.2858, "river_grid"),
    "Geneva": EuropeanCitySeed(46.2044, 6.1432, "lake_grid"),
    "Basel": EuropeanCitySeed(47.5596, 7.5886, "river_grid"),
    "Bern": EuropeanCitySeed(46.9480, 7.4474, "hilly_river"),
    "Lausanne": EuropeanCitySeed(46.5197, 6.6323, "lake_hilly"),
    # Central, eastern and south-eastern Europe
    "Brno": EuropeanCitySeed(49.1951, 16.6068, "mixed"),
    "Ostrava": EuropeanCitySeed(49.8209, 18.2625, "grid"),
    "Košice": EuropeanCitySeed(48.7164, 21.2611, "grid"),
    "Cluj-Napoca": EuropeanCitySeed(46.7712, 23.6236, "hilly_mixed"),
    "Timișoara": EuropeanCitySeed(45.7489, 21.2087, "radial_grid"),
    "Iași": EuropeanCitySeed(47.1585, 27.6014, "hilly_grid"),
    "Varna": EuropeanCitySeed(43.2141, 27.9147, "coastal_grid"),
    "Plovdiv": EuropeanCitySeed(42.1354, 24.7453, "hilly_grid"),
    "Thessaloniki": EuropeanCitySeed(40.6401, 22.9444, "coastal_grid", "large"),
    "Patras": EuropeanCitySeed(38.2466, 21.7346, "coastal_grid"),
    "Split": EuropeanCitySeed(43.5081, 16.4402, "coastal_hilly"),
    "Rijeka": EuropeanCitySeed(45.3271, 14.4422, "coastal_hilly"),
    "Sarajevo": EuropeanCitySeed(43.8563, 18.4131, "mountain_mixed"),
    "Belgrade": EuropeanCitySeed(44.7866, 20.4489, "river_grid", "large"),
    "Novi Sad": EuropeanCitySeed(45.2671, 19.8335, "river_grid"),
    "Skopje": EuropeanCitySeed(41.9973, 21.4280, "river_grid"),
    "Tirana": EuropeanCitySeed(41.3275, 19.8187, "radial_grid", "large"),
    "Podgorica": EuropeanCitySeed(42.4304, 19.2594, "river_grid"),
    "Pristina": EuropeanCitySeed(42.6629, 21.1655, "hilly_grid"),
    "Vilnius": EuropeanCitySeed(54.6872, 25.2797, "hilly_river"),
    "Kaunas": EuropeanCitySeed(54.8985, 23.9036, "river_grid"),
    "Tartu": EuropeanCitySeed(58.3776, 26.7290, "river_grid", "compact"),
}


_PROFILE_TEXT: Final[dict[str, str]] = {
    "grid": (
        "Its dense, connected and regular street grid supports moderate or detailed continuous outlines. "
        "Start with rotations near 0 or 90 degrees and keep the route inside the central urban fabric."
    ),
    "mixed": (
        "Its connected street network mixes ordered blocks with an irregular historic core. "
        "Place compact or medium outlines just outside the oldest streets and test several rotations."
    ),
    "radial_grid": (
        "Its dense, connected network combines radial and concentric avenues with a regular outer grid. "
        "Rounded silhouettes fit the centre; orthogonal outlines fit the surrounding districts."
    ),
    "river_grid": (
        "It has a dense, connected and mostly regular street grid divided by a major river. "
        "Keep the complete shape on one bank where possible and avoid unnecessary bridge crossings."
    ),
    "river_mixed": (
        "A major river and an irregular historic core constrain an otherwise connected urban network. "
        "Use compact continuous outlines on one bank and prefer simpler shapes near the centre."
    ),
    "hilly_river": (
        "A river and hilly, winding districts create strong barriers in the connected street network. "
        "Keep shapes compact, on one bank, and use low-to-moderate detail after testing orientations."
    ),
    "canal_grid": (
        "Its dense, connected grid is interrupted by rivers or canals. Keep the drawing on one connected "
        "street cluster, limit bridge crossings, and favour compact continuous outlines."
    ),
    "coastal_grid": (
        "Its dense, mostly regular street grid meets a coast or harbour. Place the whole outline inland "
        "from the waterfront; compact shapes and rotations aligned with the grid are strong choices."
    ),
    "coastal_mixed": (
        "Its connected but partly irregular street network is constrained by the coast. Keep the route "
        "inland and use compact, continuous silhouettes that tolerate several tested rotations."
    ),
    "coastal_hilly": (
        "The coast and hilly, winding terrain constrain the connected street network. Place small or medium "
        "continuous outlines inland, avoid steep edges, and reduce fine detail."
    ),
    "coastal_river": (
        "The connected street network is divided by both a river and coastal water. Keep the shape in one "
        "urban sector, avoid repeated bridge crossings, and prefer compact continuous outlines."
    ),
    "hilly_grid": (
        "It has a usable regular street grid with hilly or winding edges. Place the route on the flatter, "
        "connected blocks and use moderate detail with a few tested rotations."
    ),
    "hilly_mixed": (
        "Its connected street network is hilly and partly irregular. Keep shapes compact, avoid sparse slopes, "
        "and favour simple continuous outlines over fragile detail."
    ),
    "mountain_grid": (
        "A regular urban grid is tightly bounded by mountain terrain. Keep the route in the flat connected "
        "core, away from steep outer roads; compact orthogonal shapes are the safest fit."
    ),
    "mountain_mixed": (
        "Mountain terrain and winding streets constrain the connected urban basin. Use compact, low-detail "
        "outlines near the centre and avoid sparse slopes."
    ),
    "mountain_river": (
        "Mountain terrain and a river constrain the connected urban corridor. Keep compact shapes on the "
        "flatter streets on one bank and avoid both steep roads and repeated crossings."
    ),
    "lake_grid": (
        "Its dense, connected grid is divided by a lake or major lakeside edge. Keep the outline on one land "
        "sector, avoid water crossings, and use compact grid-aligned silhouettes."
    ),
    "lake_hilly": (
        "A lakeside edge and hilly, winding terrain constrain the street network. Keep shapes compact and "
        "inland on one connected cluster, with simple continuous outlines."
    ),
}


def city_profile_text(city: str, seed: EuropeanCitySeed) -> str:
    """Return deterministic prose consumed by planning and recommendation."""

    profile = _PROFILE_TEXT[seed.profile]
    scale_hint = {
        "compact": "The compact search area is best suited to shorter routes. ",
        "large": "The broad urban fabric can support longer routes and extra detail. ",
        "medium": "The urban search area supports short and medium routes. ",
    }[seed.scale]
    return f"{city}: {profile} {scale_hint}Centre at ({seed.lat:.4f}, {seed.lon:.4f})."
