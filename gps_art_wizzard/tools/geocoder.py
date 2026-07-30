"""Geocoding via Nominatim (free, no key required).

Returns a city centre + bounding box. Falls back to the configured default
city on any error so the pipeline never hard-fails on geocoding.

Also provides :func:`city_context` — a short natural-language description of
each known city's geography (river, grid orientation, areas to avoid), which
the PlanningAgent uses for map-aware route planning.
"""

from __future__ import annotations

import logging
import re

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

BoundingBox = tuple[float, float, float, float]  # (south, north, west, east)


class GeoResult:
    def __init__(
        self,
        name: str,
        lat: float,
        lon: float,
        bbox: BoundingBox,
        *,
        substituted: bool = False,
    ):
        self.name = name
        self.lat = lat
        self.lon = lon
        self.bbox = bbox
        self.substituted = substituted


_DEFAULTS = {
    # --- Hungarian cities (primary focus) ---
    "Budapest": GeoResult("Budapest", 47.4979, 19.0402, (47.35, 47.60, 18.93, 19.30)),
    "Debrecen": GeoResult("Debrecen", 47.5316, 21.6273, (47.48, 47.58, 21.55, 21.72)),
    "Szeged": GeoResult("Szeged", 46.2530, 20.1414, (46.20, 46.30, 20.05, 20.22)),
    "Miskolc": GeoResult("Miskolc", 48.1035, 20.7784, (48.05, 48.15, 20.70, 20.85)),
    "Pécs": GeoResult("Pécs", 46.0727, 18.2323, (46.04, 46.11, 18.17, 18.30)),
    "Győr": GeoResult("Győr", 47.6875, 17.6506, (47.65, 47.73, 17.58, 17.72)),
    "Nyíregyháza": GeoResult("Nyíregyháza", 47.9555, 21.7169, (47.92, 47.99, 21.64, 21.79)),
    "Kecskemét": GeoResult("Kecskemét", 46.9068, 19.6913, (46.87, 46.94, 19.64, 19.74)),
    "Székesfehérvár": GeoResult("Székesfehérvár", 47.1894, 18.4105, (47.15, 47.23, 18.35, 18.47)),
    "Szombathely": GeoResult("Szombathely", 47.2307, 16.6215, (47.20, 47.26, 16.57, 16.67)),
    "Veszprém": GeoResult("Veszprém", 47.0935, 17.9115, (47.06, 47.13, 17.86, 17.97)),
    "Zalaegerszeg": GeoResult("Zalaegerszeg", 46.8417, 16.8416, (46.81, 46.87, 16.78, 16.90)),
    "Keszthely": GeoResult("Keszthely", 46.7671, 17.2433, (46.74, 46.80, 17.20, 17.30)),
    "Eger": GeoResult("Eger", 47.9028, 20.3723, (47.88, 47.93, 20.33, 20.42)),
    "Sopron": GeoResult("Sopron", 47.6850, 16.5880, (47.66, 47.71, 16.54, 16.63)),
    "Tatabánya": GeoResult("Tatabánya", 47.5853, 18.4041, (47.56, 47.61, 18.35, 18.46)),
    "Kaposvár": GeoResult("Kaposvár", 46.3647, 17.7941, (46.33, 46.40, 17.74, 17.84)),
    "Szekszárd": GeoResult("Szekszárd", 46.3480, 18.7066, (46.32, 46.38, 18.66, 18.75)),
    "Békéscsaba": GeoResult("Békéscsaba", 46.6825, 21.0890, (46.65, 46.71, 21.03, 21.14)),
    "Cegléd": GeoResult("Cegléd", 47.1541, 19.8145, (47.13, 47.18, 19.77, 19.85)),
    "Vac": GeoResult("Vác", 47.8900, 19.1361, (47.87, 47.91, 19.11, 19.16)),
    "Szentendre": GeoResult("Szentendre", 47.7833, 19.0744, (47.76, 47.80, 19.05, 19.10)),
    "Esztergom": GeoResult("Esztergom", 47.7939, 18.7416, (47.77, 47.82, 18.70, 18.78)),
    "Gyula": GeoResult("Gyula", 46.6431, 21.0250, (46.62, 46.67, 20.98, 21.07)),
    "Hajdúszoboszló": GeoResult("Hajdúszoboszló", 47.4310, 21.3970, (47.41, 47.45, 21.36, 21.43)),
    "Siófok": GeoResult("Siófok", 46.9036, 18.0497, (46.88, 46.93, 18.02, 18.08)),
    "Balatonfüred": GeoResult("Balatonfüred", 46.9536, 17.8890, (46.93, 46.98, 17.86, 17.92)),
    "Visegrád": GeoResult("Visegrád", 47.7969, 18.9647, (47.78, 47.81, 18.95, 18.98)),
    "Makó": GeoResult("Makó", 46.2203, 20.4817, (46.20, 46.24, 20.44, 20.52)),
    "Hódmezővásárhely": GeoResult("Hódmezővásárhely", 46.4180, 20.3310, (46.38, 46.46, 20.27, 20.39)),
    "Salgótarján": GeoResult("Salgótarján", 48.0933, 19.8031, (48.06, 48.12, 19.76, 19.84)),
    "Nagykanizsa": GeoResult("Nagykanizsa", 46.4592, 16.9917, (46.43, 46.49, 16.95, 17.03)),
    "Dunaújváros": GeoResult("Dunaújváros", 46.9654, 18.9364, (46.94, 46.99, 18.89, 18.98)),
    "Baja": GeoResult("Baja", 46.1803, 18.9531, (46.16, 46.20, 18.91, 18.99)),
    "Mosonmagyaróvár": GeoResult("Mosonmagyaróvár", 47.8683, 17.2678, (47.85, 47.89, 17.24, 17.30)),
    "Pápa": GeoResult("Pápa", 47.2625, 17.4333, (47.24, 47.29, 17.39, 17.47)),
    "Gyöngyös": GeoResult("Gyöngyös", 47.7875, 19.9306, (47.76, 47.81, 19.89, 19.97)),
    "Kisvárda": GeoResult("Kisvárda", 48.2186, 22.0789, (48.20, 48.24, 22.04, 22.12)),
    "Sárospatak": GeoResult("Sárospatak", 48.1583, 21.5750, (48.13, 48.18, 21.54, 21.61)),
    "Tokaj": GeoResult("Tokaj", 48.1236, 21.4194, (48.10, 48.14, 21.39, 21.45)),
    "Békés": GeoResult("Békés", 46.6947, 21.1164, (46.67, 46.72, 21.08, 21.15)),
    "Orosháza": GeoResult("Orosháza", 46.6011, 20.9408, (46.57, 46.63, 20.90, 20.98)),
    "Jászberény": GeoResult("Jászberény", 47.4953, 19.9186, (47.47, 47.52, 19.88, 19.96)),
    "Monor": GeoResult("Monor", 47.3511, 19.4486, (47.33, 47.37, 19.42, 19.48)),
    "Várpalota": GeoResult("Várpalota", 47.1989, 18.1361, (47.17, 47.22, 18.10, 18.17)),
    "Balatonlelle": GeoResult("Balatonlelle", 46.7772, 17.8942, (46.76, 46.80, 17.87, 17.92)),
    "Tihany": GeoResult("Tihany", 46.9133, 17.8889, (46.90, 46.93, 17.87, 17.91)),
    "Badacsony": GeoResult("Badacsony", 46.7814, 17.6314, (46.76, 46.80, 17.60, 17.66)),
    "Tapolca": GeoResult("Tapolca", 46.8722, 17.5936, (46.85, 46.89, 17.56, 17.63)),
    "Vonyarcvashegy": GeoResult("Vonyarcvashegy", 46.7794, 17.6714, (46.77, 46.79, 17.65, 17.69)),
    "Zamárdi": GeoResult("Zamárdi", 46.8953, 17.9819, (46.88, 46.91, 17.96, 18.00)),
    "Fonyód": GeoResult("Fonyód", 46.8442, 17.9864, (46.82, 46.87, 17.96, 18.01)),
    "Révfülöp": GeoResult("Révfülöp", 46.8356, 17.6903, (46.82, 46.85, 17.67, 17.71)),
    "Nagyatád": GeoResult("Nagyatád", 46.2336, 17.3564, (46.21, 46.26, 17.32, 17.39)),
    "Barcs": GeoResult("Barcs", 45.9647, 17.4747, (45.94, 45.99, 17.44, 17.51)),
    "Szentlőrinc": GeoResult("Szentlőrinc", 46.0372, 17.9708, (46.02, 46.05, 17.94, 18.00)),
    "Komló": GeoResult("Komló", 46.1989, 18.2833, (46.17, 46.22, 18.24, 18.32)),
    "Dombóvár": GeoResult("Dombóvár", 46.3750, 18.1319, (46.35, 46.40, 18.09, 18.17)),
    "Mohács": GeoResult("Mohács", 45.9950, 18.6800, (45.97, 46.02, 18.64, 18.72)),
    "Szigetvár": GeoResult("Szigetvár", 46.0392, 17.8050, (46.01, 46.07, 17.77, 17.84)),
    "Paks": GeoResult("Paks", 46.6350, 18.8597, (46.61, 46.66, 18.82, 18.90)),
    "Kalocsa": GeoResult("Kalocsa", 46.5294, 18.9747, (46.51, 46.55, 18.94, 19.01)),
    "Kiskőrös": GeoResult("Kiskőrös", 46.6214, 19.2836, (46.60, 46.64, 19.25, 19.32)),
    "Kiskunhalas": GeoResult("Kiskunhalas", 46.4303, 19.4208, (46.40, 46.46, 19.38, 19.46)),
    "Kistelek": GeoResult("Kistelek", 46.3753, 20.2622, (46.35, 46.40, 20.23, 20.29)),
    "Csongrád": GeoResult("Csongrád", 46.7050, 20.1450, (46.68, 46.73, 20.10, 20.19)),
    "Abony": GeoResult("Abony", 47.1994, 19.9686, (47.18, 47.22, 19.94, 20.00)),
    "Nagykőrös": GeoResult("Nagykőrös", 47.0533, 19.7772, (47.03, 47.08, 19.74, 19.81)),
    "Üllő": GeoResult("Üllő", 47.3858, 19.4822, (47.37, 47.40, 19.46, 19.50)),
    "Gödöllő": GeoResult("Gödöllő", 47.5944, 19.3603, (47.57, 47.62, 19.32, 19.40)),
    "Dunakeszi": GeoResult("Dunakeszi", 47.5900, 19.1389, (47.57, 47.61, 19.11, 19.17)),
    "Vác": GeoResult("Vác", 47.8900, 19.1361, (47.87, 47.91, 19.11, 19.16)),
    # --- Other major cities (still supported) ---
    "Paris": GeoResult("Paris", 48.8566, 2.3522, (48.81, 48.91, 2.25, 2.42)),
    "Berlin": GeoResult("Berlin", 52.5200, 13.4050, (52.33, 52.68, 13.08, 13.76)),
    "London": GeoResult("London", 51.5074, -0.1278, (51.35, 51.70, -0.50, 0.30)),
    "New York": GeoResult("New York", 40.7128, -74.0060, (40.50, 40.90, -74.20, -73.70)),
    "Vienna": GeoResult("Vienna", 48.2082, 16.3738, (48.11, 48.33, 16.18, 16.58)),
    "Barcelona": GeoResult("Barcelona", 41.3851, 2.1734, (41.32, 41.46, 2.08, 2.23)),
    "Amsterdam": GeoResult("Amsterdam", 52.3676, 4.9041, (52.27, 52.43, 4.73, 5.07)),
    "Prague": GeoResult("Prague", 50.0755, 14.4378, (49.94, 50.18, 14.22, 14.71)),
}

# Natural-language geography per city — fed to the PlanningAgent so it can
# reason about where to place the shape and what to avoid. Keys are matched
# case-insensitively against the geocoded city name.
_CITY_GEOGRAPHY: dict[str, str] = {
    "budapest": (
        "The Danube river runs north-south through the centre, splitting Buda (west, hilly, sparse roads) "
        "from Pest (east, flat, dense grid). Place shapes on the Pest side (east of the river, "
        "around lat 47.49-47.52, lon 19.05-19.10) for the best street grid. Avoid the river itself "
        "and the Buda hills to the west. The Pest grid runs roughly N-S/E-W, so rotation ~0 or ~90. "
        "Margitsziget island and Városliget park are obstacles. District VII/VIII (Erzsébetváros/Józsefváros) "
        "has the densest grid. For larger shapes, use District IX-XI south of the centre."
    ),
    "debrecen": (
        "Debrecen is on the Great Hungarian Plain — flat terrain with a near-regular street grid. "
        "The city centre (lat 47.53, lon 21.63) has a radial-concentric layout around the Great Church "
        "(Nagytemplom). The outer districts have a rectilinear grid. Place shapes 1-2 km from the centre "
        "in any direction. Avoid the Nagyerdő park/forest to the northwest (around lat 47.55, lon 21.60). "
        "No major rivers. Grid runs N-S/E-W, rotation ~0 or ~90. Excellent for GPS art — flat and dense."
    ),
    "szeged": (
        "The Tisza river runs through Szeged from northeast to southwest. The city centre has a "
        "radial-concentric layout (Körtár streets form rings) with avenues radiating from the centre. "
        "Place shapes west of the Tisza (lat 46.24-46.27, lon 20.12-20.16) on the regular grid. "
        "Avoid the Tisza river. The inner ring roads (Körös, Tisza Lajos krt) are good shape corridors. "
        "Rotation ~0 aligns with the grid. The Tisza bends — keep shapes west of the river."
    ),
    "miskolc": (
        "Miskolc is in a valley between the Bükk hills (north) and the Miskolc basin. The Sajó river "
        "flows through the eastern side. The city centre has an irregular grid, but the southern "
        "districts (lat 48.07-48.10, lon 20.76-20.80) are more regular. Avoid the Sajó river (east), "
        "Bükk mountains (north), and Avas hill (centre). Place shapes south of the centre. "
        "Grid runs roughly E-W, rotation ~0. Keep shapes compact (3-15 km)."
    ),
    "pécs": (
        "Pécs is built on the southern slopes of the Mecsek hills. The historic centre has irregular, "
        "winding streets (hard for shapes). The southern districts (lat 46.05-46.08, lon 18.21-18.26) "
        "are flatter with a more regular grid. Avoid the Mecsek hills to the north. Place shapes "
        "south of the centre. Grid runs roughly N-S/E-W. Keep shapes compact (3-12 km)."
    ),
    "győr": (
        "Győr sits at the confluence of the Rába, Rábca, and Danube rivers. The inner city has a "
        "compact grid, but rivers split it into sections. Place shapes north of the Rába (lat 47.68-47.71, "
        "lon 17.63-17.68) on the regular grid. Avoid all three rivers — the Danube to the east, Rába to "
        "the south. Grid runs N-S/E-W, rotation ~0. The Győr-Sopron road axis is a good corridor."
    ),
    "nyíregyháza": (
        "Nyíregyháza is on the Nyírség plain — flat terrain with a regular grid. The city centre "
        "(lat 47.96, lon 21.72) has a near-rectilinear layout. No major rivers. The Sóstó (Salt Lake) "
        "and its park/forest lie to the northwest (avoid). Place shapes east or south of the centre. "
        "Grid runs N-S/E-W, rotation ~0 or ~90. Excellent for GPS art — flat and regular."
    ),
    "kecskemét": (
        "Kecskemét is on the Great Hungarian Plain — flat with a radial-concentric grid. The centre "
        "has avenues radiating from Kossuth Square. The outer districts have a rectilinear grid. "
        "No major rivers. Place shapes 1-2 km from the centre. Grid runs N-S/E-W, rotation ~0. "
        "Good for GPS art. Keep shapes 5-20 km."
    ),
    "székesfehérvár": (
        "Székesfehérvár has a fairly regular grid in the centre and northern districts. No major "
        "rivers. Place shapes around lat 47.18-47.22, lon 18.38-18.44. Avoid the industrial zones "
        "to the southeast. Grid runs N-S/E-W, rotation ~0. Good for compact to medium shapes (3-15 km)."
    ),
    "szombathely": (
        "Szombathely is in western Hungary, flat with a regular grid. The Gyöngy stream runs through "
        "the south — avoid it. Place shapes north of the stream (lat 47.21-47.25, lon 16.60-16.65). "
        "Grid runs N-S/E-W, rotation ~0. Good for compact shapes (3-12 km)."
    ),
    "veszprém": (
        "Veszprém is built on hills — the terrain is uneven and streets are winding. The castle "
        "district (north) is very irregular. Place shapes south of the centre (lat 47.06-47.10, "
        "lon 17.89-17.94) where the grid is more regular. Avoid the Séd stream valley. "
        "Keep shapes compact (3-10 km). Expect more refinement iterations."
    ),
    "zalaegerszeg": (
        "Zalaegerszeg is in western Hungary, hilly terrain with an irregular grid. The Zala river "
        "runs through the eastern side. Place shapes west of the Zala (lat 46.83-46.86, lon 16.80-16.87). "
        "Avoid the river. Grid is irregular — rotation matters less. Keep shapes compact (3-10 km)."
    ),
    "keszthely": (
        "Lake Balaton lies directly south of the town centre. Place shapes NORTH of the lake, "
        "in the town grid (lat 46.77-46.80, lon 17.22-17.27). Avoid the lake shore to the "
        "south — routes crossing water will fail. The town grid is small and irregular, so "
        "keep shapes compact (3-8 km) and expect refinement."
    ),
    "eger": (
        "Eger is in a valley in the Bükk hills. The Egri stream runs through the centre. The "
        "historic centre has winding streets. Place shapes south of the stream (lat 47.89-47.92, "
        "lon 20.35-20.40) on the more regular grid. Avoid the hills to the north. "
        "Keep shapes compact (3-10 km)."
    ),
    "sopron": (
        "Sopron is near the Austrian border, built on the slopes of the Sopron mountains. The "
        "inner city has a medieval radial layout. The eastern districts (lat 47.68-47.71, "
        "lon 16.60-16.63) are flatter with a more regular grid. Avoid the hills to the west. "
        "Keep shapes compact (3-12 km)."
    ),
    "tatabánya": (
        "Tatabánya is in the Tata-Környe basin, flat with a regular grid. No major rivers. "
        "Place shapes west of the M1 around lat 47.57-47.60, lon 18.37-18.40, where the urban "
        "street grid is denser. Avoid the Gerecse hills and sparse trails east of the motorway. "
        "Grid runs N-S/E-W, rotation ~0. Good for compact to medium shapes (3-15 km)."
    ),
    "kaposvár": (
        "Kaposvár is in Somogy county, the Kapos river runs through the centre. Place shapes "
        "south of the river (lat 46.34-46.39, lon 17.77-17.83) on the regular grid. Avoid the "
        "river. Grid runs roughly E-W. Keep shapes compact (3-12 km)."
    ),
    "szekszárd": (
        "Szekszárd is in Tolna county, built on hills. The historic centre has winding streets. "
        "The northern districts (lat 46.35-46.38, lon 18.68-18.73) are more regular. Avoid the "
        "Wöhr wine region hills. Keep shapes compact (3-10 km)."
    ),
    "békéscsaba": (
        "Békéscsaba is on the Great Hungarian Plain — flat with a regular grid. The Körös river "
        "system is to the east — avoid. Place shapes west of the river (lat 46.66-46.70, "
        "lon 21.04-21.12). Grid runs N-S/E-W, rotation ~0. Good for GPS art."
    ),
    "cegléd": (
        "Cegléd is on the Great Hungarian Plain — flat with a near-perfect rectilinear grid. "
        "No major rivers or obstacles. Place shapes around the centre (lat 47.15, lon 19.81). "
        "Grid runs N-S/E-W, rotation ~0 or ~90. Excellent for GPS art — clean grid, no obstacles."
    ),
    "siófok": (
        "Siófok is on the southern shore of Lake Balaton. The Sió river exits the lake here. "
        "Place shapes SOUTH of the lake (lat 46.88-46.92, lon 18.03-18.08). Avoid the lake to "
        "the north and the Sió river. Grid runs N-S/E-W. Keep shapes compact (3-10 km)."
    ),
    "hajdúszoboszló": (
        "Hajdúszoboszló is on the Great Hungarian Plain — flat with a regular grid. Famous spa town. "
        "No major rivers. Place shapes around the centre (lat 47.43, lon 21.40). Grid runs N-S/E-W. "
        "Good for compact shapes (3-12 km)."
    ),
    "makó": (
        "Makó is on the Great Hungarian Plain near the Maros river. Place shapes north of the Maros "
        "(lat 46.21-46.24, lon 20.46-20.50). Avoid the river to the south. Grid runs N-S/E-W. "
        "Good for compact shapes (3-10 km)."
    ),
    "hódmezővásárhely": (
        "Hódmezővásárhely is on the Great Hungarian Plain — flat with a regular grid. The Tisza river "
        "is to the east — avoid. Place shapes around the centre (lat 46.42, lon 20.33). "
        "Grid runs N-S/E-W, rotation ~0. Good for GPS art."
    ),
    "salgótarján": (
        "Salgótarján is in Nógrád county, in a valley surrounded by hills. The Tarján stream runs through. "
        "Place shapes in the central valley (lat 48.08-48.11, lon 19.78-19.82). Avoid the hills. "
        "Grid is irregular. Keep shapes compact (3-8 km)."
    ),
    "nagykanizsa": (
        "Nagykanizsa is in Zala county, flat with a regular grid. The Zala river is to the west — avoid. "
        "Place shapes east of the river (lat 46.44-46.48, lon 16.98-17.03). Grid runs N-S/E-W. "
        "Good for compact shapes (3-12 km)."
    ),
    "dunaújváros": (
        "Dunaújváros is on the Danube — the river is the western boundary. Place shapes east of the "
        "Danube (lat 46.94-46.98, lon 18.92-18.98). Avoid the river. The city has a planned grid. "
        "Rotation ~0. Good for medium shapes (5-15 km)."
    ),
    "baja": (
        "Baja is on the Danube and Sugovica stream. Place shapes east of the Danube (lat 46.17-46.20, "
        "lon 18.93-18.99). Avoid the river to the west. Grid runs N-S/E-W. Keep shapes compact (3-10 km)."
    ),
    "gyöngyös": (
        "Gyöngyös is at the foot of the Mátra mountains. The Kánya stream runs through. Place shapes "
        "south of the stream (lat 47.77-47.80, lon 19.91-19.96). Avoid the Mátra hills to the north. "
        "Grid runs N-S/E-W. Good for compact shapes (3-12 km)."
    ),
    "pápa": (
        "Pápa is in Veszprém county, the Tapolca stream runs through. Place shapes north of the stream "
        "(lat 47.25-47.28, lon 17.41-17.46). Avoid the Bakony hills to the south. Grid runs N-S/E-W. "
        "Good for compact shapes (3-12 km)."
    ),
    "jászberény": (
        "Jászberény is on the Great Hungarian Plain — flat with a regular grid. The Zagyva river runs "
        "through the centre. Place shapes east of the Zagyva (lat 47.49-47.51, lon 19.92-19.96). "
        "Grid runs N-S/E-W. Good for GPS art."
    ),
    "gödöllő": (
        "Gödöllő is NE of Budapest, hilly terrain with a semi-regular grid. Place shapes around the "
        "centre (lat 47.59, lon 19.36). Avoid the royal palace grounds. Grid runs roughly N-S/E-W. "
        "Good for compact shapes (3-10 km)."
    ),
    "dunakeszi": (
        "Dunakeszi is north of Budapest on the Danube's left (east) bank. Place shapes east of the "
        "Danube (lat 47.58-47.61, lon 19.13-19.17). Avoid the river to the west. Grid runs N-S. "
        "Good for compact shapes (3-10 km)."
    ),
    "tapolca": (
        "Tapolca is in the Balaton Uplands, near Lake Balaton's northern shore. The Tapolca stream "
        "runs through the town. Place shapes NORTH of the stream, away from the lake (lat 46.86-46.89, "
        "lon 17.57-17.62). Avoid Lake Balaton to the south and the basalt hills (Badacsony) to the "
        "southwest. Grid is small and irregular. Keep shapes compact (3-8 km)."
    ),
    "vonyarcvashegy": (
        "Vonyarcvashegy is a small village on the northern shore of Lake Balaton, between Keszthely "
        "and Badacsony. The town is compact with a single main road along the shore. Place shapes "
        "NORTH of the lake, on the hillside roads (lat 46.77-46.79, lon 17.66-17.69). Avoid the lake "
        "to the south. Streets are very limited — keep shapes very compact (2-5 km). Expect significant "
        "refinement due to sparse road network."
    ),
    "paks": (
        "Paks is on the Danube in Tolna county. Place shapes east of the Danube (lat 46.62-46.66, "
        "lon 18.83-18.90). Avoid the river to the west. Grid runs N-S/E-W. Keep shapes compact (3-12 km)."
    ),
    "kalocsa": (
        "Kalocsa is on the Great Hungarian Plain — flat with a regular grid. No major rivers nearby. "
        "Place shapes around the centre (lat 46.53, lon 18.97). Grid runs N-S/E-W. Excellent for GPS art."
    ),
    "nagykőrös": (
        "Nagykőrös is on the Great Hungarian Plain — flat with a near-perfect rectilinear grid. "
        "No rivers. Place shapes around the centre (lat 47.05, lon 19.78). Grid runs N-S/E-W. "
        "Excellent for GPS art — clean grid, no obstacles."
    ),
    "csongrád": (
        "Csongrád is at the confluence of the Tisza and Körös rivers. Place shapes WEST of the Tisza "
        "(lat 46.69-46.72, lon 20.10-20.18). Avoid both rivers. Grid runs N-S/E-W. Keep shapes compact (3-10 km)."
    ),
    "orosháza": (
        "Orosháza is on the Great Hungarian Plain — flat with a regular grid. No major rivers. "
        "Place shapes around the centre (lat 46.60, lon 20.94). Grid runs N-S/E-W. Good for GPS art."
    ),
    "mohács": (
        "Mohács is on the Danube in Baranya county. Place shapes east of the Danube (lat 46.00-46.03, "
        "lon 18.67-18.72). Avoid the river to the west. Grid runs N-S/E-W. Keep shapes compact (3-10 km)."
    ),
    "komló": (
        "Komló is in the Mecsek hills — hilly, irregular streets. Place shapes in the central valley "
        "(lat 46.18-46.21, lon 18.26-18.31). Avoid the surrounding hills. Keep shapes compact (3-8 km)."
    ),
    "paris": (
        "The Seine river curves through the centre from east to west. The central arrondissements "
        "(1-11) have a Haussmann grid with broad avenues, good for shapes. Avoid the Seine bends, "
        "the Bois de Boulogne (west), and Bois de Vincennes (east). Place around lat 48.85-48.88, "
        "lon 2.33-2.40. Streets radiate from several étoiles (stars), so rotation ~30 or ~60 can "
        "align with major avenues."
    ),
    "berlin": (
        "The Spree river meanders east of the centre. Mitte and Prenzlauer Berg (lat 52.51-52.54, "
        "lon 13.38-13.44) have a fairly regular grid, good for shapes. Avoid the Spree, the "
        "Tiergarten park (west), and Tempelhofer Feld (south). The grid runs roughly NW-SE in "
        "Mitte, so rotation ~30 works well. The wall's former path has discontinuities."
    ),
    "london": (
        "The Thames river curves through the centre. The City and Westminster have dense but "
        "irregular streets — hard for clean shapes. Better areas: Islington/Hackney (lat "
        "51.53-51.56, lon -0.10 to -0.05) or Southwark (south of river). Avoid the Thames, "
        "Hyde Park, and Regent's Park. Streets are irregular, so rotation matters less — "
        "expect more refinement iterations."
    ),
    "new york": (
        "Manhattan has a near-perfect grid N-S/E-W above 14th Street. Place shapes in Midtown "
        "or the Upper East/ West Side (lat 40.74-40.79, lon -74.00 to -73.95). Avoid the "
        "Hudson and East Rivers, Central Park (lat 40.77-40.81, lon -73.97 to -73.96), and "
        "below 14th St (irregular). Rotation ~30 aligns with Broadway's diagonal. "
        "Excellent grid city — shapes snap cleanly here."
    ),
    "vienna": (
        "The Danube (Donau) runs through the east side. The Innenstadt (1st district) is a "
        "compact ring grid, good for small shapes. Favor the districts 2-9 (lat 48.20-48.25, "
        "lon 16.35-16.45) for larger shapes. Avoid the Danube and the Prater park to the "
        "east. The Gürtel ring road gives a roughly circular reference — rotation ~0 or ~90."
    ),
    "barcelona": (
        "L'Eixample has a near-perfect octagonal grid (Cerdà plan) — excellent for GPS art. "
        "Place shapes around lat 41.38-41.41, lon 2.14-2.19. Avoid the Mediterranean coast "
        "(south), Ciutat Vella (old town, irregular), and Parc de la Ciutadella. The grid "
        "runs NW-SE, so rotation ~0 or ~90. One of the best grid cities for clean shapes."
    ),
    "amsterdam": (
        "The Grachtengordel canal ring creates a semicircular grid in the centre. The "
        "Jordaan and Canal Belt (lat 52.36-52.38, lon 4.88-4.90) work for small shapes. "
        "Avoid the IJ waterway to the north and Vondelpark to the south. Streets curve "
        "along canals, so expect distortion. The Polder area west of the centre has "
        "straighter roads."
    ),
    "prague": (
        "The Vltava river curves through the centre. Vinohrady and Žižkov (lat 50.07-50.09, "
        "lon 14.43-14.47) have a regular grid on the east side, good for shapes. Avoid the "
        "river, Prague Castle area (west, hilly), and Petřín park. The eastern grid runs "
        "roughly N-S/E-W. Old town streets are too irregular for clean shapes."
    ),
}


def _known_default(city: str) -> GeoResult | None:
    query = city.casefold().strip()
    for name, result in _DEFAULTS.items():
        if name.casefold() == query:
            return result
    for name, res in _DEFAULTS.items():
        if re.search(
            rf"(?<!\w){re.escape(name.casefold())}(?!\w)",
            query,
        ):
            return res
    return None


def _default(city: str) -> GeoResult:
    known = _known_default(city)
    if known is not None:
        return known
    fallback = _DEFAULTS["Budapest"]
    return GeoResult(
        fallback.name,
        fallback.lat,
        fallback.lon,
        fallback.bbox,
        substituted=True,
    )


def geocode(city: str) -> GeoResult:
    """Geocode a city name. Never raises — falls back to a built-in default."""
    import os

    known = _known_default(city)
    if known is not None:
        # The curated database includes route-oriented bounding boxes and
        # geography for supported cities. It is faster and more reliable than
        # making a public Nominatim request only to fall back after rate limits.
        return known

    if os.getenv("GEOCODE_OFFLINE"):
        return _default(city)

    cfg = get_settings().geocoder
    headers = {
        "User-Agent": (
            f"GPS-Art-Wizard/0.1 ({cfg.nominatim_email})"
            if cfg.nominatim_email
            else "GPS-Art-Wizard/0.1"
        ),
        "Accept-Language": "en",
    }
    params: dict[str, str | int] = {
        "q": city,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    if cfg.nominatim_email:
        # Nominatim documents the email query parameter for identifying
        # applications; it also avoids anonymous-request rejection on some
        # public deployments.
        params["email"] = cfg.nominatim_email
    url = f"{cfg.nominatim_base_url}/search"
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        if data:
            hit = data[0]
            lat = float(hit["lat"])
            lon = float(hit["lon"])
            bb = hit.get("boundingbox", ["47.35", "47.60", "18.93", "19.30"])
            south, north, west, east = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
            name = hit.get("display_name", city).split(",")[0]
            return GeoResult(name, lat, lon, (south, north, west, east))
    except Exception as e:  # noqa: BLE001
        log.warning("Nominatim geocode failed for %r (%s) — using built-in default", city, e)

    return _default(city)


def city_context(city: str, geo_result: GeoResult) -> str:
    """Return a natural-language geography description for map-aware planning.

    Falls back to a generic description derived from the bounding box when the
    city is not in the known-geography database.
    """
    low = (city or "").lower()
    for key, desc in _CITY_GEOGRAPHY.items():
        if key in low or low in key:
            return desc
    # Generic fallback: describe the bbox dimensions.
    south, north, west, east = geo_result.bbox
    from . import geo as _geo
    cy = (south + north) / 2
    h = _geo.haversine(south, west, north, west)
    w = _geo.haversine(cy, west, cy, east)
    heading = _geo.bbox_long_axis_heading(geo_result.bbox)
    return (
        f"City spans ~{w/1000:.0f} km E-W and ~{h/1000:.0f} km N-S. "
        f"City bounding-box long-axis heading ~{heading:.0f}° (not measured street bearing). "
        f"Centre at ({geo_result.lat:.4f}, {geo_result.lon:.4f}). "
        f"No specific water/park obstacles known — place near the centre and "
        f"expect the refinement loop to handle local issues."
    )
