"""Geocoding via Nominatim (free, no key required).

Returns a city centre + bounding box. Falls back to the configured default
city on any error so the pipeline never hard-fails on geocoding.

Also provides :func:`city_context` — a short natural-language description of
each known city's geography (river, grid orientation, areas to avoid), which
the PlanningAgent uses for map-aware route planning.
"""

from __future__ import annotations

import logging
import math
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
    # Remaining settlements in the KSH 2025 top 50 that were not already in
    # the local catalogue. Centres follow OpenStreetMap/Nominatim; the tighter
    # boxes deliberately focus placement search on the continuous urban grid.
    "Érd": GeoResult("Érd", 47.3772, 18.9214, (47.33, 47.42, 18.85, 18.97)),
    "Szolnok": GeoResult("Szolnok", 47.1754, 20.1946, (47.13, 47.22, 20.11, 20.25)),
    "Szigetszentmiklós": GeoResult(
        "Szigetszentmiklós", 47.3487, 19.0452, (47.31, 47.40, 18.99, 19.11)
    ),
    "Ózd": GeoResult("Ózd", 48.2192, 20.2811, (48.17, 48.27, 20.20, 20.39)),
    "Hajdúböszörmény": GeoResult(
        "Hajdúböszörmény", 47.6717, 21.5079, (47.61, 47.73, 21.39, 21.59)
    ),
    "Budaörs": GeoResult("Budaörs", 47.4611, 18.9612, (47.42, 47.49, 18.88, 18.99)),
    "Kiskunfélegyháza": GeoResult(
        "Kiskunfélegyháza", 46.7114, 19.8502, (46.65, 46.77, 19.77, 19.94)
    ),
    "Ajka": GeoResult("Ajka", 47.1057, 17.5587, (47.04, 47.15, 17.49, 17.65)),
    "Szentes": GeoResult("Szentes", 46.6524, 20.2566, (46.60, 46.72, 20.17, 20.36)),
    "Gyál": GeoResult("Gyál", 47.3845, 19.2173, (47.34, 47.41, 19.17, 19.27)),
    "Dunaharaszti": GeoResult(
        "Dunaharaszti", 47.3542, 19.0912, (47.30, 47.39, 19.05, 19.16)
    ),
    "Tata": GeoResult("Tata", 47.6516, 18.3282, (47.59, 47.69, 18.23, 18.43)),
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
    # Lake Balaton shore municipalities from Annex 1/2 of Act CXII of
    # 2000.  These route-oriented boxes stay close to each settlement's
    # continuous street network instead of copying water-heavy administrative
    # boundaries from the geocoder.
    "Alsóörs": GeoResult("Alsóörs", 46.9883, 17.9771, (46.970, 47.006, 17.955, 18.004)),
    "Aszófő": GeoResult("Aszófő", 46.9289, 17.8334, (46.916, 46.943, 17.814, 17.853)),
    "Ábrahámhegy": GeoResult("Ábrahámhegy", 46.8148, 17.5715, (46.800, 46.830, 17.550, 17.594)),
    "Badacsonytomaj": GeoResult(
        "Badacsonytomaj", 46.8058, 17.5147, (46.780, 46.827, 17.486, 17.543)
    ),
    "Badacsonytördemic": GeoResult(
        "Badacsonytördemic", 46.8120, 17.4737, (46.794, 46.824, 17.458, 17.497)
    ),
    "Balatonakali": GeoResult(
        "Balatonakali", 46.8837, 17.7527, (46.865, 46.902, 17.724, 17.783)
    ),
    "Balatonakarattya": GeoResult(
        "Balatonakarattya", 47.0240, 18.1439, (47.002, 47.045, 18.110, 18.180)
    ),
    "Balatonalmádi": GeoResult(
        "Balatonalmádi", 47.0303, 18.0156, (47.000, 47.063, 17.980, 18.058)
    ),
    "Balatonberény": GeoResult(
        "Balatonberény", 46.7108, 17.3193, (46.691, 46.731, 17.288, 17.348)
    ),
    "Balatonboglár": GeoResult(
        "Balatonboglár", 46.7785, 17.6553, (46.752, 46.803, 17.620, 17.696)
    ),
    "Balatonederics": GeoResult(
        "Balatonederics", 46.8091, 17.3813, (46.788, 46.827, 17.352, 17.414)
    ),
    "Balatonfenyves": GeoResult(
        "Balatonfenyves", 46.7177, 17.4945, (46.687, 46.748, 17.451, 17.522)
    ),
    "Balatonfőkajár": GeoResult(
        "Balatonfőkajár", 47.0203, 18.2122, (46.995, 47.047, 18.174, 18.252)
    ),
    "Balatonföldvár": GeoResult(
        "Balatonföldvár", 46.8491, 17.8792, (46.829, 46.871, 17.849, 17.904)
    ),
    "Balatonfűzfő": GeoResult(
        "Balatonfűzfő", 47.0620, 18.0410, (47.045, 47.087, 18.007, 18.068)
    ),
    "Balatongyörök": GeoResult(
        "Balatongyörök", 46.7616, 17.3505, (46.746, 46.784, 17.320, 17.389)
    ),
    "Balatonkenese": GeoResult(
        "Balatonkenese", 47.0355, 18.1087, (47.008, 47.062, 18.071, 18.143)
    ),
    "Balatonkeresztúr": GeoResult(
        "Balatonkeresztúr", 46.6977, 17.3704, (46.681, 46.724, 17.337, 17.414)
    ),
    "Balatonmáriafürdő": GeoResult(
        "Balatonmáriafürdő", 46.7050, 17.3718, (46.690, 46.738, 17.338, 17.416)
    ),
    "Balatonőszöd": GeoResult(
        "Balatonőszöd", 46.8069, 17.8002, (46.785, 46.837, 17.766, 17.828)
    ),
    "Balatonrendes": GeoResult(
        "Balatonrendes", 46.8274, 17.5858, (46.807, 46.841, 17.561, 17.619)
    ),
    "Balatonszabadi": GeoResult(
        "Balatonszabadi", 46.8913, 18.1336, (46.871, 46.921, 18.096, 18.181)
    ),
    "Balatonszárszó": GeoResult(
        "Balatonszárszó", 46.8263, 17.8342, (46.805, 46.858, 17.799, 17.879)
    ),
    "Balatonszemes": GeoResult(
        "Balatonszemes", 46.8060, 17.7790, (46.782, 46.838, 17.739, 17.807)
    ),
    "Balatonszentgyörgy": GeoResult(
        "Balatonszentgyörgy", 46.6922, 17.3000, (46.667, 46.721, 17.267, 17.337)
    ),
    "Balatonszepezd": GeoResult(
        "Balatonszepezd", 46.8518, 17.6638, (46.830, 46.872, 17.635, 17.707)
    ),
    "Balatonudvari": GeoResult(
        "Balatonudvari", 46.9054, 17.8048, (46.884, 46.923, 17.779, 17.843)
    ),
    "Balatonvilágos": GeoResult(
        "Balatonvilágos", 46.9642, 18.1593, (46.944, 46.992, 18.110, 18.199)
    ),
    "Csopak": GeoResult("Csopak", 46.9797, 17.9231, (46.958, 47.001, 17.894, 17.958)),
    "Gyenesdiás": GeoResult(
        "Gyenesdiás", 46.7725, 17.2860, (46.753, 46.800, 17.264, 17.323)
    ),
    "Kővágóörs": GeoResult(
        "Kővágóörs", 46.8490, 17.6016, (46.824, 46.874, 17.568, 17.638)
    ),
    "Örvényes": GeoResult("Örvényes", 46.9148, 17.8165, (46.901, 46.931, 17.795, 17.837)),
    "Paloznak": GeoResult("Paloznak", 46.9833, 17.9409, (46.961, 47.005, 17.912, 17.971)),
    "Szántód": GeoResult("Szántód", 46.8694, 17.9045, (46.850, 46.889, 17.879, 17.936)),
    "Szigliget": GeoResult("Szigliget", 46.7990, 17.4354, (46.776, 46.825, 17.405, 17.468)),
    "Zánka": GeoResult("Zánka", 46.8729, 17.6834, (46.850, 46.895, 17.648, 17.727)),
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
    "Madrid": GeoResult("Madrid", 40.4168, -3.7035, (40.31, 40.55, -3.82, -3.55)),
    "Rome": GeoResult("Rome", 41.8933, 12.4829, (41.80, 42.00, 12.35, 12.65)),
    "Lisbon": GeoResult("Lisbon", 38.7078, -9.1366, (38.69, 38.80, -9.23, -9.08)),
    "Brussels": GeoResult("Brussels", 50.8467, 4.3525, (50.79, 50.92, 4.30, 4.45)),
    "Copenhagen": GeoResult("Copenhagen", 55.6867, 12.5701, (55.53, 55.85, 12.41, 12.73)),
    "Stockholm": GeoResult("Stockholm", 59.3251, 18.0711, (59.17, 59.49, 17.91, 18.23)),
    "Oslo": GeoResult("Oslo", 59.9133, 10.7390, (59.81, 60.05, 10.49, 10.95)),
    "Helsinki": GeoResult("Helsinki", 60.1666, 24.9435, (59.92, 60.30, 24.78, 25.25)),
    "Warsaw": GeoResult("Warsaw", 52.2334, 21.0711, (52.10, 52.37, 20.85, 21.28)),
    "Kraków": GeoResult("Kraków", 50.0469, 19.9972, (49.96, 50.13, 19.79, 20.22)),
    "Bratislava": GeoResult("Bratislava", 48.1517, 17.1093, (48.01, 48.27, 16.94, 17.29)),
    "Ljubljana": GeoResult("Ljubljana", 46.0500, 14.5069, (45.89, 46.21, 14.34, 14.67)),
    "Zagreb": GeoResult("Zagreb", 45.8131, 15.9773, (45.61, 45.97, 15.77, 16.24)),
    "Bucharest": GeoResult("Bucharest", 44.4361, 26.1027, (44.33, 44.55, 25.96, 26.23)),
    "Sofia": GeoResult("Sofia", 42.6977, 23.3217, (42.56, 42.87, 23.16, 23.63)),
    "Athens": GeoResult("Athens", 37.9756, 23.7348, (37.82, 38.14, 23.57, 23.90)),
    "Dublin": GeoResult("Dublin", 53.3494, -6.2606, (53.29, 53.42, -6.39, -6.11)),
    "Munich": GeoResult("Munich", 48.1371, 11.5754, (48.06, 48.25, 11.36, 11.73)),
    "Milan": GeoResult("Milan", 45.4642, 9.1896, (45.38, 45.54, 9.04, 9.28)),
    "Porto": GeoResult("Porto", 41.1502, -8.6103, (41.13, 41.19, -8.70, -8.55)),
    "Zurich": GeoResult("Zurich", 47.3744, 8.5410, (47.32, 47.44, 8.44, 8.63)),
    "Tallinn": GeoResult("Tallinn", 59.4372, 24.7573, (59.35, 59.60, 24.55, 24.93)),
    "Riga": GeoResult("Riga", 56.9494, 24.1052, (56.85, 57.09, 23.93, 24.33)),
}

# The 50 largest Hungarian settlements by KSH resident population on
# 2025-01-01.  Keeping this public, ordered tuple lets deterministic intent
# parsing and the UI share a clearly defined coverage target.
MAJOR_HUNGARIAN_CITIES = (
    "Budapest", "Debrecen", "Szeged", "Miskolc", "Pécs", "Győr",
    "Nyíregyháza", "Kecskemét", "Székesfehérvár", "Szombathely", "Érd",
    "Szolnok", "Tatabánya", "Sopron", "Kaposvár", "Veszprém",
    "Zalaegerszeg", "Békéscsaba", "Eger", "Dunakeszi", "Nagykanizsa",
    "Hódmezővásárhely", "Dunaújváros", "Szigetszentmiklós", "Cegléd", "Vác",
    "Mosonmagyaróvár", "Gödöllő", "Baja", "Salgótarján", "Ózd", "Szekszárd",
    "Hajdúböszörmény", "Budaörs", "Esztergom", "Szentendre",
    "Kiskunfélegyháza", "Pápa", "Gyula", "Gyöngyös", "Ajka", "Kiskunhalas",
    "Jászberény", "Orosháza", "Szentes", "Gyál", "Hajdúszoboszló", "Siófok",
    "Dunaharaszti", "Tata",
)

# The current Lake Balaton shore-municipality list from Annex 1/2 of
# Act CXII of 2000.  Near-shore settlements marked with an asterisk in the
# source are intentionally excluded.  Siófok also appears in the KSH top 50,
# so consumers should deduplicate when presenting both groups.
# https://njt.hu/jogszabaly/2000-112-00-00
BALATON_SHORE_CITIES = (
    "Alsóörs", "Aszófő", "Ábrahámhegy", "Badacsonytomaj",
    "Badacsonytördemic", "Balatonakali", "Balatonakarattya", "Balatonalmádi",
    "Balatonberény", "Balatonboglár", "Balatonederics", "Balatonfenyves",
    "Balatonfőkajár", "Balatonföldvár", "Balatonfüred", "Balatonfűzfő",
    "Balatongyörök", "Balatonkenese", "Balatonkeresztúr", "Balatonlelle",
    "Balatonmáriafürdő", "Balatonőszöd", "Balatonrendes", "Balatonszabadi",
    "Balatonszárszó", "Balatonszemes", "Balatonszentgyörgy", "Balatonszepezd",
    "Balatonudvari", "Balatonvilágos", "Csopak", "Fonyód", "Gyenesdiás",
    "Keszthely", "Kővágóörs", "Örvényes", "Paloznak", "Révfülöp",
    "Siófok", "Szántód", "Szigliget", "Tihany", "Vonyarcvashegy", "Zamárdi",
    "Zánka",
)

# A regionally balanced European set based on cities covered by Eurostat's
# city-statistics framework. This is a product coverage list, not a population
# ranking or a claim that every neighbourhood is equally suitable for GPS art.
MAJOR_EUROPEAN_CITIES = (
    "London", "Paris", "Berlin", "Madrid", "Rome", "Barcelona", "Vienna",
    "Amsterdam", "Prague", "Brussels", "Copenhagen", "Stockholm", "Oslo",
    "Helsinki", "Warsaw", "Kraków", "Bratislava", "Ljubljana", "Zagreb",
    "Bucharest", "Sofia", "Athens", "Dublin", "Munich", "Milan", "Lisbon",
    "Porto", "Zurich", "Tallinn", "Riga",
)

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
    "érd": (
        "Érd has a fragmented suburban street network with hillier western and northern districts. "
        "Place shapes southeast of the centre on the denser, flatter grid and keep them compact. "
        "Avoid the Danube floodplain at the eastern edge. Irregular streets favour simple outlines."
    ),
    "szolnok": (
        "Szolnok is flat, but the Tisza and Zagyva split the road network. Place shapes west of the "
        "Tisza on the connected central and western grid. Avoid forced river crossings. Rotation ~0 "
        "or ~90 suits the mostly rectilinear districts; medium shapes work well."
    ),
    "szigetszentmiklós": (
        "Szigetszentmiklós lies on Csepel Island between Danube branches. Its suburban grid is "
        "elongated north-south. Place compact shapes around the central urban area and avoid both "
        "riverbanks, industrial parcels, and placements that require leaving the island."
    ),
    "ózd": (
        "Ózd occupies a narrow, hilly valley with an irregular street network. Place small shapes "
        "along the connected central valley and avoid the surrounding slopes and sparse outer roads. "
        "Use simple outlines and expect more refinement."
    ),
    "hajdúböszörmény": (
        "Hajdúböszörmény is flat and has a distinctive ring-and-radial centre with rectilinear outer "
        "districts. There are no major river barriers. Place medium shapes just outside the inner "
        "ring; rotations ~0, ~45, or ~90 can align well with its street structure."
    ),
    "budaörs": (
        "Budaörs is constrained by the Buda Hills to the north and major transport corridors to the "
        "south. Place compact shapes on the connected central and eastern street grid, away from the "
        "steep northern slopes and motorway. Irregular terrain favours simpler outlines."
    ),
    "kiskunfélegyháza": (
        "Kiskunfélegyháza is flat with a dense radial centre and regular outer grid. It has no major "
        "water barrier through the urban core. Place medium shapes around the centre; rotation ~0 or "
        "~90 is a strong starting point. Good for more detailed GPS art."
    ),
    "ajka": (
        "Ajka has rolling terrain, separated neighbourhoods, and industrial areas. Place compact "
        "shapes on the connected central grid, avoiding the industrial west and sparse hills. "
        "Simple silhouettes are more reliable than fine detail."
    ),
    "szentes": (
        "Szentes is flat with a regular urban grid, but the Kurca watercourse crosses the city. "
        "Place shapes within one connected side of the Kurca where possible and avoid unnecessary "
        "bridge crossings. Rotation ~0 or ~90 and medium outlines are good starting choices."
    ),
    "gyál": (
        "Gyál is flat and suburban with a mostly rectilinear street grid. Place compact or medium "
        "shapes around the centre, away from the motorway and airport-side industrial edges. "
        "Rotation ~0 or ~90 generally follows the street pattern."
    ),
    "dunaharaszti": (
        "Dunaharaszti is a flat suburban town beside the Danube and Ráckeve branch. Place compact "
        "shapes on the continuous eastern urban grid and avoid the riverbanks, islands, and railway "
        "barriers. The north-south street pattern favours rotation ~0."
    ),
    "tata": (
        "Tata has a usable urban grid around several large lakes. Place compact shapes north or east "
        "of Öreg-tó, keeping the whole outline on one connected street area. Avoid Öreg-tó, Cseke-tó, "
        "and the hillier, sparser edges; expect water-aware placement to matter."
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
    "madrid": (
        "Madrid has a dense radial core and more regular grids in Salamanca and the eastern districts. "
        "Place medium shapes east or northeast of the historic centre. Avoid Retiro and Casa de Campo "
        "parks and unnecessary crossings of the Manzanares. Several grid bearings make rotation search important."
    ),
    "rome": (
        "Rome combines a very irregular historic centre with the Tiber and large archaeological areas. "
        "Use compact shapes in a single connected district such as Prati or the flatter southern/eastern grid. "
        "Avoid crossing the Tiber, Villa Borghese, and archaeological parks unless the route is explicitly verified."
    ),
    "lisbon": (
        "Lisbon is hilly and bordered by the Tagus to the south. The Baixa grid is small; Avenidas Novas "
        "and northern districts offer longer connected streets. Place compact shapes north of the river, "
        "avoid the waterfront and steep Alfama streets, and expect rotation and scale to matter."
    ),
    "brussels": (
        "Brussels has a radial inner pentagon and mixed but dense outer grids. The canal lies west of the "
        "centre and large parks interrupt the east. Place shapes within one connected eastern or southern "
        "district and search several rotations rather than assuming a single grid bearing."
    ),
    "copenhagen": (
        "Copenhagen is flat with dense walking and cycling connections, but the harbour and canals split "
        "the centre. Place shapes west of the inner harbour around Frederiksberg, Nørrebro, or Vesterbro. "
        "Avoid water crossings and large parks; compact and medium outlines have several route alternatives."
    ),
    "stockholm": (
        "Stockholm is built across islands, so water connectivity dominates placement. Keep the entire shape "
        "inside one mainland or large-island street area such as Vasastan or Södermalm. Avoid narrow bridge "
        "dependencies and use compact outlines; a visually close point across water may require a long detour."
    ),
    "oslo": (
        "Oslo opens onto the fjord in the south and becomes hillier to the north. Place compact shapes on the "
        "connected inner east or west grid, away from the waterfront and forested slopes. Irregular bearings "
        "make measured placement more useful than a fixed orientation."
    ),
    "helsinki": (
        "Helsinki has a clear central grid but a highly indented coastline and many islands. Keep shapes on the "
        "main peninsula or within one inland district, avoiding harbour inlets and shoreline parks. The central "
        "grid supports compact geometry; larger art needs careful water-aware placement."
    ),
    "warsaw": (
        "Warsaw is mostly flat with broad, connected grids west of the Vistula. Place medium or detailed shapes "
        "in central and western districts, avoiding river crossings and very large parks. Multiple planning-era "
        "grids use different bearings, so rotation search is valuable."
    ),
    "kraków": (
        "Kraków has an irregular historic core enclosed by Planty and the Vistula to the south. Place compact "
        "shapes north or east of the old town on denser grids, keeping them on one side of the river. Avoid "
        "Planty, Błonia, and the medieval centre for detailed outlines."
    ),
    "bratislava": (
        "Bratislava is bounded by the Danube to the south and the Little Carpathians to the north. Place compact "
        "or medium shapes east or northeast of the old town on flatter streets. Avoid river crossings, castle "
        "slopes, and the sparse northern hills."
    ),
    "ljubljana": (
        "Ljubljana is compact and mostly flat, with the Ljubljanica winding through the centre. Place shapes north "
        "or east of the historic core within one connected grid, avoiding the river bends, Tivoli Park, and the "
        "castle hill. Compact outlines suit the available urban scale."
    ),
    "zagreb": (
        "Zagreb has a strong east-west lower-city grid between Medvednica and the Sava. Place medium shapes on the "
        "flat central or eastern grid. Avoid the steep northern districts, railway yards, and forced crossings "
        "toward the Sava; rotation ~0 or ~90 is a useful starting point."
    ),
    "bucharest": (
        "Bucharest is flat with a dense mixture of radial boulevards and rectilinear neighbourhoods. Place medium "
        "or detailed shapes north or east of the centre, avoiding the largest parks and repeated Dâmbovița "
        "crossings. Several orientations should be screened because adjacent districts use different grids."
    ),
    "sofia": (
        "Sofia has a dense central grid but rises toward Vitosha in the south. Place compact or medium shapes in "
        "central, northern, or eastern districts. Avoid the mountain-facing southern edge and large parks; the "
        "flatter grid supports simple and moderately detailed silhouettes."
    ),
    "athens": (
        "Athens has a dense but irregular street network interrupted by hills and archaeological sites. Place "
        "compact shapes in a single flatter northern or eastern neighbourhood. Avoid Lycabettus, the Acropolis "
        "area, and large parks; expect more placement and rotation refinement than in a regular grid city."
    ),
    "dublin": (
        "The Liffey divides Dublin east-west. Georgian districts provide local grids, while Phoenix Park and the "
        "docklands create large gaps. Place compact shapes on one side of the river, preferably south or north "
        "of the centre, and avoid unnecessary bridge dependence."
    ),
    "munich": (
        "Munich is mostly flat with dense connected streets, but the Isar and Englischer Garten interrupt the "
        "eastern side. Place medium shapes west or south of the centre within one grid area. Multiple radial and "
        "rectilinear patterns make several tested orientations preferable to one fixed bearing."
    ),
    "milan": (
        "Milan is flat and dense, with ring-and-radial streets overlaid by several regular grids. Place medium or "
        "detailed shapes outside the tight historic core, avoiding rail yards and the largest parks. The connected "
        "street fabric supports multiple orientations and comparatively complex outlines."
    ),
    "porto": (
        "Porto is hilly and bounded by the Douro to the south. Place compact shapes north or east of the historic "
        "centre on one connected street area. Avoid the river, steep Ribeira lanes, and bridge-dependent routes; "
        "simple outlines are more reliable than fine detail."
    ),
    "zurich": (
        "Lake Zurich lies south of the centre and the Limmat divides the inner city. Place compact shapes north or "
        "west of the lake within one connected district. Avoid water, steep outer hills, and large rail areas; "
        "the available grids are local rather than city-wide."
    ),
    "tallinn": (
        "Tallinn is mostly flat, but the medieval old town and Baltic shoreline interrupt the grid. Place compact "
        "or medium shapes east or south of the old town on planned streets. Avoid the harbour, Ülemiste lake, and "
        "the walled centre for complex silhouettes."
    ),
    "riga": (
        "Riga is flat with a strong rectilinear grid on the east bank of the Daugava. Place medium shapes east of "
        "the river, avoiding bridge crossings, the old town, and large rail yards. Rotation ~0 or ~90 is a good "
        "starting point and the connected grid can support detailed outlines."
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

# Lake Balaton needs more specific placement guidance than an ordinary city
# bbox: the lake, the shore railway/road corridors, hills on the north shore,
# and wetlands in the west can all turn a visually good template into an
# unroutable trace.  Profiles also describe the local street density so the
# shape recommender can reduce detail in small or constrained settlements.
_CITY_GEOGRAPHY.update({
    "alsóörs": (
        "Alsóörs is a small, hilly north-shore settlement with Lake Balaton to the south. "
        "Keep compact shapes on one connected inland street cluster, north of the railway and shore road where "
        "possible. The sloping, irregular and fairly sparse network favours simple continuous outlines."
    ),
    "aszófő": (
        "Aszófő has a small, sparse street network on rising ground north of Lake Balaton. Keep the drawing "
        "compact around the village, avoid the lakeshore, railway and wetlands toward the Tihany basin, and do "
        "not rely on fine detail. East-west-oriented simple outlines fit the narrow land corridor best."
    ),
    "ábrahámhegy": (
        "Ábrahámhegy occupies a narrow, hilly strip north of Lake Balaton. The shore railway and Route 71 "
        "divide a sparse, irregular network, so place small shapes inland on one connected side of those barriers. "
        "Simple elongated silhouettes are more reliable than detailed or circular ones."
    ),
    "badacsonytomaj": (
        "Badacsonytomaj is constrained between Lake Balaton to the south and the steep Badacsony volcanic hill. "
        "Use compact, simple shapes within one connected neighbourhood and avoid climbing roads, vineyards, the "
        "shore railway and water. The terrain and fragmented settlements make fine detail fragile."
    ),
    "badacsonytördemic": (
        "Badacsonytördemic has a sparse, irregular network between Lake Balaton and the steep Badacsony slopes. "
        "Keep small continuous outlines in the village street cluster, avoiding the railway, Route 71, vineyards "
        "and water. Low-detail shapes are the safest recommendation."
    ),
    "balatonakali": (
        "Balatonakali is a small north-shore settlement with the lake to the south and rolling hills inland. "
        "Place compact shapes north of the railway on connected village streets. The sparse network and shore "
        "barriers favour simple, moderately elongated outlines aligned roughly east-west."
    ),
    "balatonakarattya": (
        "Balatonakarattya sits on a high, hilly bluff above the eastern basin, with Lake Balaton to the west and "
        "southwest. Keep compact shapes on the connected plateau streets and avoid steep shore access roads, the "
        "railway and water. Irregular streets favour simple outlines over detailed templates."
    ),
    "balatonalmádi": (
        "Balatonalmádi wraps around the northeast shore and rises into wooded hills. Place compact shapes within "
        "one connected central or northern neighbourhood, away from Lake Balaton, rail crossings and steep outer "
        "roads. Its hilly, irregular network supports moderate detail only after testing several placements."
    ),
    "balatonberény": (
        "Balatonberény is a small, mostly flat southwest-shore settlement with Lake Balaton to the north. Keep "
        "compact shapes on the connected grid south of the railway, avoiding the shore, wetlands and large "
        "agricultural gaps. Simple orthogonal outlines work best."
    ),
    "balatonboglár": (
        "Balatonboglár has a fairly connected, mostly regular grid south of Lake Balaton, interrupted by the "
        "railway, Route 7 and the Vár-hegy area. Use the flatter central and southern streets for medium shapes, "
        "avoid the shore and hill, and start with east-west or north-south orientations."
    ),
    "balatonederics": (
        "Balatonederics lies between the lake basin, wetlands and the steep Keszthely Hills. Its street network is "
        "small, sparse and irregular. Keep shapes compact in the village core, avoid Route 71, the railway, water "
        "and hillside tracks, and recommend simple continuous silhouettes."
    ),
    "balatonfenyves": (
        "Balatonfenyves is flat and strongly elongated along the south shore, with Lake Balaton to the north and "
        "wetlands and canals inland. Use the connected residential streets on one side of the railway; elongated "
        "east-west outlines fit better than tall shapes. Avoid water, rail crossings and sparse outer areas."
    ),
    "balatonfőkajár": (
        "Balatonfőkajár is inland from the northeast shore and has a small, sparse village network. It is less "
        "water-constrained than most Balaton settlements, but the M7 and agricultural gaps limit continuity. Keep "
        "shapes compact around the connected core and prefer low-detail outlines."
    ),
    "balatonföldvár": (
        "Balatonföldvár has a compact, connected south-shore grid with Lake Balaton to the north and rising "
        "ground to the south. Place small or medium shapes south of the railway without crossing Route 7 repeatedly. "
        "The local grid can support moderate detail, especially in east-west orientations."
    ),
    "balatonfüred": (
        "Balatonfüred has one of the larger connected north-shore street networks, with Lake Balaton to the south "
        "and hills to the north. Place medium shapes on the flatter central and eastern grid, north of the railway, "
        "and avoid the shore, steep outer roads and large park areas. Moderate detail and several orientations are viable."
    ),
    "balatonfűzfő": (
        "Balatonfűzfő has separated neighbourhoods around the northeast basin, with the lake to the south and "
        "industrial land between street clusters. Keep compact shapes within one connected residential area and "
        "avoid water, rail lines, industrial parcels and steep links. Simple outlines are the most reliable."
    ),
    "balatongyörök": (
        "Balatongyörök is a narrow, hilly settlement between Lake Balaton to the south and the Keszthely Hills. "
        "Keep compact shapes on one connected street cluster north of the railway and Route 71. Sparse hillside "
        "roads and water barriers favour simple east-west-oriented outlines."
    ),
    "balatonkenese": (
        "Balatonkenese sits on hilly bluffs at the lake's eastern end. Place compact shapes on connected plateau "
        "streets, away from Lake Balaton, steep shore approaches, the railway and large gullies. The irregular "
        "network favours simple continuous outlines and a few tested rotations."
    ),
    "balatonkeresztúr": (
        "Balatonkeresztúr is flat and set just inland from the southwest shore. Its connected village grid can "
        "support compact orthogonal shapes, but the railway, Route 7, canals and gaps between settlements are "
        "barriers. Keep the route in one street cluster and avoid extending north into the lakefront strip."
    ),
    "balatonlelle": (
        "Balatonlelle has a flat, connected and fairly regular south-shore grid with Lake Balaton to the north. "
        "Place medium shapes south of the railway while avoiding Route 7 and the M7 corridor farther inland. "
        "East-west or north-south orientations can support moderate detail without repeated barrier crossings."
    ),
    "balatonmáriafürdő": (
        "Balatonmáriafürdő is flat and elongated along the southwest shore, with the lake to the north and "
        "canals and wetlands inland. Keep compact shapes on one side of the railway in the connected residential "
        "strip. Simple east-west silhouettes are safer than tall or highly detailed shapes."
    ),
    "balatonőszöd": (
        "Balatonőszöd has a small, sparse south-shore network separated from the lakefront by rail and road "
        "corridors. Use the compact inland village grid, avoid Lake Balaton, Route 7, the M7 and agricultural gaps, "
        "and prefer simple continuous outlines."
    ),
    "balatonrendes": (
        "Balatonrendes is a very small, hilly north-shore settlement with a sparse and fragmented street network. "
        "Keep the drawing compact and inland, avoiding Lake Balaton, the railway, Route 71 and quarry or vineyard "
        "tracks. Only simple low-detail silhouettes are likely to remain recognisable."
    ),
    "balatonszabadi": (
        "Balatonszabadi is flat and mostly inland east of Siófok. The central village has a usable regular grid, "
        "while the railway, M7 and disconnected lakeside district create barriers. Place compact or medium shapes "
        "in one connected core; orthogonal outlines and rotations near 0 or 90 degrees are good starting points."
    ),
    "balatonszárszó": (
        "Balatonszárszó has a compact south-shore grid with Lake Balaton to the north. Keep small or medium shapes "
        "south of the railway and within the connected town streets, avoiding Route 7, the M7 and wooded gaps. "
        "Moderately simple east-west-oriented outlines fit the corridor well."
    ),
    "balatonszemes": (
        "Balatonszemes is mostly flat with a connected south-shore street grid. Place compact or medium shapes "
        "south of the railway, avoiding Lake Balaton, Route 7 and the M7 corridor. The grid supports moderate detail, "
        "with east-west or north-south orientations as strong starting points."
    ),
    "balatonszentgyörgy": (
        "Balatonszentgyörgy lies by the marshy western basin and is crossed by major rail and road corridors. "
        "Keep compact shapes in the connected village core, away from wetlands, canals, rail yards and Route 7. "
        "The sparse network favours simple continuous outlines."
    ),
    "balatonszepezd": (
        "Balatonszepezd is a narrow, hilly north-shore settlement with Lake Balaton to the south. The railway, "
        "Route 71 and sparse hillside roads leave little continuous space. Use small east-west-oriented outlines "
        "within one street cluster and avoid fine detail."
    ),
    "balatonudvari": (
        "Balatonudvari has a small, sparse network on rolling ground north of Lake Balaton. Keep shapes compact "
        "and inland, on one connected side of the railway and Route 71. Simple elongated silhouettes cope best "
        "with the narrow shore corridor and irregular local streets."
    ),
    "balatonvilágos": (
        "Balatonvilágos extends along a high bluff above the lake's eastern shore. Keep compact shapes on connected "
        "streets away from the steep edge, Lake Balaton, the railway and M7 approaches. Its elongated, partly "
        "irregular network favours simple outlines aligned with the shore."
    ),
    "csopak": (
        "Csopak is a compact, hilly north-shore settlement with Lake Balaton to the south. Place small shapes on "
        "the connected inland streets north of the railway and avoid the shore, Route 71 and steep vineyard roads. "
        "Simple or moderately detailed continuous outlines work better than intricate templates."
    ),
    "fonyód": (
        "Fonyód combines a connected south-shore street network with two prominent hills and Lake Balaton to the "
        "north. Place compact or medium shapes on flatter streets south or east of the hills, avoiding the shore, "
        "railway and steep winding roads. Moderate detail is possible after testing several placements."
    ),
    "gyenesdiás": (
        "Gyenesdiás has a connected but sloping street network between Lake Balaton to the south and the Keszthely "
        "Hills. Keep compact or medium shapes north of the railway and away from steep forest roads. Moderate detail "
        "can work on the denser lower grid; elongated east-west outlines fit the corridor."
    ),
    "keszthely": (
        "Keszthely has the largest dense, connected and fairly regular grid on Balaton's western shore, with the "
        "lake to the east. Place medium or detailed shapes west of the shore and south of the hillier outer areas. "
        "Avoid the waterfront, railway, Helikon park and large institutional blocks; multiple orientations are viable."
    ),
    "kővágóörs": (
        "Kővágóörs sits inland on rolling, hilly terrain north of the shore. Its sparse, irregular village "
        "roads are separated from lakeside neighbourhoods and quarry areas. Keep shapes compact in one connected "
        "cluster and recommend simple low-detail outlines."
    ),
    "örvényes": (
        "Örvényes is a very small north-shore village with sparse streets between Lake Balaton and rolling "
        "hills. Keep the route compact and inland, avoid the railway, Route 71 and water, and use a simple continuous "
        "outline; intricate templates exceed the available network detail."
    ),
    "paloznak": (
        "Paloznak is a small, hilly village above the north shore with a sparse and irregular street network. Place "
        "compact shapes within the connected village core, avoiding steep vineyard roads, Route 71 and Lake Balaton. "
        "Simple low-detail outlines are the reliable choice."
    ),
    "révfülöp": (
        "Révfülöp occupies a narrow, hilly strip north of Lake Balaton. Keep compact shapes on connected "
        "inland streets, avoid the railway, Route 71, water and steep outer roads, and favour simple east-west "
        "silhouettes over detailed templates."
    ),
    "siófok": (
        "Siófok has the largest flat, connected and regular grid on the south shore, with Lake Balaton to the north. "
        "Place medium or detailed shapes south of the railway and keep them on one side of the Sió channel. Avoid "
        "the shore, M7 and large rail areas; rotations near 0 or 90 degrees align well with the grid."
    ),
    "szántód": (
        "Szántód has a small, flat network at the narrowest part of the lake, beside ferry facilities and wetlands. "
        "Use compact shapes south of the railway within one connected residential cluster. Avoid Lake Balaton, "
        "marshy areas, Route 7 and routes that depend on the ferry."
    ),
    "szigliget": (
        "Szigliget is a small peninsula-like settlement constrained by Lake Balaton, wetlands and a steep volcanic "
        "castle hill. Streets are sparse, winding and irregular. Keep shapes very compact on lower connected roads, "
        "avoid water and hillside tracks, and recommend only simple continuous outlines."
    ),
    "tihany": (
        "Tihany is a narrow, hilly peninsula surrounded by Lake Balaton and split by the Inner Lake and protected "
        "land. Its streets are sparse and winding. Keep shapes very compact within one connected village area, avoid "
        "water, trails and ferry dependence, and use simple low-detail outlines."
    ),
    "vonyarcvashegy": (
        "Vonyarcvashegy has a connected but sloping east-west street network between Lake Balaton and the Keszthely "
        "Hills. Keep compact shapes north of the railway and away from the waterfront and steep forest roads. "
        "Simple or moderate elongated outlines fit better than tall, intricate shapes."
    ),
    "zamárdi": (
        "Zamárdi is mostly flat with a connected south-shore grid, Lake Balaton to the north and the M7 to the south. "
        "Place compact or medium shapes between the railway and motorway without repeated crossings. East-west or "
        "north-south orientations support moderate detail; avoid the shore and large camping areas."
    ),
    "zánka": (
        "Zánka is a small, hilly north-shore settlement with the lake to the south and separated institutional land "
        "to the east. Keep compact shapes in the connected village streets north of the railway and Route 71. "
        "Sparse, irregular roads favour simple east-west-oriented outlines."
    ),
})


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


def _route_search_bbox(lat: float, lon: float, value: object) -> BoundingBox:
    """Return a finite urban search box, not an unbounded admin region."""
    half_lat = 0.04
    half_lon = 0.06
    if isinstance(value, list | tuple) and len(value) >= 4:
        try:
            south, north, west, east = (float(item) for item in value[:4])
        except (TypeError, ValueError):
            pass
        else:
            if (
                all(math.isfinite(item) for item in (south, north, west, east))
                and -90 <= south < north <= 90
                and -180 <= west < east <= 180
            ):
                # Municipality boundaries can cover lakes, forests, or large
                # rural areas. A bounded box keeps the 180-placement search
                # around the returned settlement centre.
                half_lat = min(0.08, max(0.02, (north - south) / 2.0))
                half_lon = min(0.12, max(0.03, (east - west) / 2.0))
    return (
        max(-90.0, lat - half_lat),
        min(90.0, lat + half_lat),
        max(-180.0, lon - half_lon),
        min(180.0, lon + half_lon),
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
        # Unknown prompts should resolve to inhabited places, not a same-name
        # shop, mountain, railway feature, or lake.
        "layer": "address",
        "featureType": "settlement",
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
            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                raise ValueError("geocoder returned invalid coordinates")
            bbox = _route_search_bbox(lat, lon, hit.get("boundingbox"))
            name = hit.get("display_name", city).split(",")[0]
            return GeoResult(name, lat, lon, bbox)
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
