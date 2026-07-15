import json
import os
import math
import random

DATA_DIR = r"C:\PathForge\data"
CITIES_FILE = os.path.join(DATA_DIR, "seed", "cities.json")
ARTWORKS_FILE = os.path.join(DATA_DIR, "seed", "artworks.json")
SHAPES_DIR = os.path.join(DATA_DIR, "shapes")

# 1. 100 European Cities
# (Name, Country, CountryCode, Lat, Lon, HasRiver, BridgeCount)
EUROPEAN_CITIES = [
    ("London", "United Kingdom", "UK", 51.5074, -0.1278, True, 35),
    ("Paris", "France", "FR", 48.8566, 2.3522, True, 37),
    ("Berlin", "Germany", "DE", 52.5200, 13.4050, True, 900),
    ("Madrid", "Spain", "ES", 40.4168, -3.7038, True, 0),
    ("Rome", "Italy", "IT", 41.9028, 12.4964, True, 10),
    ("Vienna", "Austria", "AT", 48.2082, 16.3738, True, 10),
    ("Bucharest", "Romania", "RO", 44.4268, 26.1025, True, 0),
    ("Prague", "Czechia", "CZ", 50.0755, 14.4378, True, 18),
    ("Warsaw", "Poland", "PL", 52.2297, 21.0122, True, 9),
    ("Stockholm", "Sweden", "SE", 59.3293, 18.0686, True, 50),
    ("Amsterdam", "Netherlands", "NL", 52.3676, 4.9041, True, 1200),
    ("Brussels", "Belgium", "BE", 50.8503, 4.3517, False, 0),
    ("Munich", "Germany", "DE", 48.1351, 11.5820, True, 0),
    ("Milan", "Italy", "IT", 45.4642, 9.1900, False, 0),
    ("Barcelona", "Spain", "ES", 41.3851, 2.1734, False, 0),
    ("Athens", "Greece", "GR", 37.9838, 23.7275, False, 0),
    ("Lisbon", "Portugal", "PT", 38.7223, -9.1393, True, 2),
    ("Dublin", "Ireland", "IE", 53.3498, -6.2603, True, 20),
    ("Copenhagen", "Denmark", "DK", 55.6761, 12.5683, True, 15),
    ("Helsinki", "Finland", "FI", 60.1695, 24.9354, False, 0),
    ("Oslo", "Norway", "NO", 59.9139, 10.7522, True, 0),
    ("Zurich", "Switzerland", "CH", 47.3769, 8.5417, True, 20),
    ("Geneva", "Switzerland", "CH", 46.2044, 6.1432, True, 5),
    ("Krakow", "Poland", "PL", 50.0647, 19.9450, True, 5),
    ("Wroclaw", "Poland", "PL", 51.1079, 17.0385, True, 100),
    ("Riga", "Latvia", "LV", 56.9496, 24.1052, True, 5),
    ("Vilnius", "Lithuania", "LT", 54.6872, 25.2797, True, 5),
    ("Tallinn", "Estonia", "EE", 59.4370, 24.7536, False, 0),
    ("Bratislava", "Slovakia", "SK", 48.1486, 17.1077, True, 5),
    ("Ljubljana", "Slovenia", "SI", 46.0569, 14.5058, True, 10),
    ("Zagreb", "Croatia", "HR", 45.8150, 15.9819, True, 0),
    ("Belgrade", "Serbia", "RS", 44.7866, 20.4489, True, 10),
    ("Sofia", "Bulgaria", "BG", 42.6977, 23.3219, False, 0),
    ("Sarajevo", "Bosnia and Herzegovina", "BA", 43.8563, 18.4131, True, 10),
    ("Skopje", "North Macedonia", "MK", 42.0024, 21.4361, True, 5),
    ("Tirana", "Albania", "AL", 41.3275, 19.8187, False, 0),
    ("Reykjavik", "Iceland", "IS", 64.1466, -21.9426, False, 0),
    ("Hamburg", "Germany", "DE", 53.5511, 9.9937, True, 2500),
    ("Frankfurt", "Germany", "DE", 50.1109, 8.6821, True, 10),
    ("Stuttgart", "Germany", "DE", 48.7758, 9.1829, True, 0),
    ("Dusseldorf", "Germany", "DE", 51.2277, 6.7735, True, 5),
    ("Cologne", "Germany", "DE", 50.9375, 6.9603, True, 5),
    ("Leipzig", "Germany", "DE", 51.3397, 12.3731, True, 0),
    ("Dresden", "Germany", "DE", 51.0504, 13.7373, True, 5),
    ("Nuremberg", "Germany", "DE", 49.4521, 11.0767, True, 0),
    ("Hanover", "Germany", "DE", 52.3759, 9.7320, True, 0),
    ("Bremen", "Germany", "DE", 53.0793, 8.8017, True, 0),
    ("Lyon", "France", "FR", 45.7640, 4.8357, True, 10),
    ("Marseille", "France", "FR", 43.2965, 5.3698, False, 0),
    ("Toulouse", "France", "FR", 43.6047, 1.4442, True, 5),
    ("Bordeaux", "France", "FR", 44.8378, -0.5792, True, 5),
    ("Lille", "France", "FR", 50.6292, 3.0573, False, 0),
    ("Nice", "France", "FR", 43.7102, 7.2620, False, 0),
    ("Nantes", "France", "FR", 47.2184, -1.5536, True, 5),
    ("Strasbourg", "France", "FR", 48.5734, 7.7521, True, 20),
    ("Montpellier", "France", "FR", 43.6108, 3.8767, False, 0),
    ("Rennes", "France", "FR", 48.1173, -1.6778, True, 0),
    ("Turin", "Italy", "IT", 45.0703, 7.6869, True, 5),
    ("Naples", "Italy", "IT", 40.8518, 14.2681, False, 0),
    ("Florence", "Italy", "IT", 43.7696, 11.2558, True, 5),
    ("Venice", "Italy", "IT", 45.4408, 12.3155, True, 400),
    ("Bologna", "Italy", "IT", 44.4949, 11.3426, False, 0),
    ("Genoa", "Italy", "IT", 44.4056, 8.9463, False, 0),
    ("Palermo", "Italy", "IT", 38.1157, 13.3615, False, 0),
    ("Valencia", "Spain", "ES", 39.4699, -0.3774, True, 0),
    ("Seville", "Spain", "ES", 37.3891, -5.9845, True, 5),
    ("Zaragoza", "Spain", "ES", 41.6488, -0.8891, True, 5),
    ("Malaga", "Spain", "ES", 36.7213, -4.4214, False, 0),
    ("Murcia", "Spain", "ES", 37.9922, -1.1307, True, 0),
    ("Palma", "Spain", "ES", 39.5696, 2.6502, False, 0),
    ("Las Palmas", "Spain", "ES", 28.1235, -15.4363, False, 0),
    ("Bilbao", "Spain", "ES", 43.2630, -2.9350, True, 5),
    ("Porto", "Portugal", "PT", 41.1579, -8.6291, True, 6),
    ("Braga", "Portugal", "PT", 41.5454, -8.4265, False, 0),
    ("Coimbra", "Portugal", "PT", 40.2033, -8.4103, True, 3),
    ("Antwerp", "Belgium", "BE", 51.2194, 4.4025, True, 5),
    ("Ghent", "Belgium", "BE", 51.0500, 3.7167, True, 10),
    ("Charleroi", "Belgium", "BE", 50.4108, 4.4446, True, 0),
    ("Liege", "Belgium", "BE", 50.6326, 5.5697, True, 5),
    ("Rotterdam", "Netherlands", "NL", 51.9225, 4.4791, True, 20),
    ("The Hague", "Netherlands", "NL", 52.0705, 4.3007, False, 0),
    ("Utrecht", "Netherlands", "NL", 52.0907, 5.1214, True, 50),
    ("Eindhoven", "Netherlands", "NL", 51.4416, 5.4697, False, 0),
    ("Gothenburg", "Sweden", "SE", 57.7089, 11.9746, True, 5),
    ("Malmo", "Sweden", "SE", 55.6049, 13.0038, False, 0),
    ("Aarhus", "Denmark", "DK", 56.1629, 10.2039, False, 0),
    ("Odense", "Denmark", "DK", 55.4991, 10.4074, True, 0),
    ("Tampere", "Finland", "FI", 61.4978, 23.7610, True, 0),
    ("Turku", "Finland", "FI", 60.4518, 22.2666, True, 5),
    ("Bergen", "Norway", "NO", 60.3913, 5.3221, False, 0),
    ("Trondheim", "Norway", "NO", 63.4305, 10.3951, True, 5),
    ("Stavanger", "Norway", "NO", 58.9690, 5.7331, False, 0),
    ("Basel", "Switzerland", "CH", 47.5596, 7.5886, True, 5),
    ("Lausanne", "Switzerland", "CH", 46.5197, 6.6323, False, 0),
    ("Bern", "Switzerland", "CH", 46.9480, 7.4474, True, 5),
    ("Linz", "Austria", "AT", 48.3069, 14.2858, True, 5),
    ("Salzburg", "Austria", "AT", 47.8095, 13.0550, True, 10),
    ("Innsbruck", "Austria", "AT", 47.2692, 11.4041, True, 5),
    ("Graz", "Austria", "AT", 47.0707, 15.4395, True, 10),
    ("Cluj-Napoca", "Romania", "RO", 46.7712, 23.6236, True, 0)
]

def add_cities():
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    existing_ids = {c["id"] for c in data["items"]}
    added = 0
    for name, country, code, lat, lon, has_river, bridges in EUROPEAN_CITIES:
        cid = name.lower().replace(" ", "-")
        if cid in existing_ids:
            continue
        c_item = {
            "id": cid,
            "name": name,
            "country": country,
            "country_code": code,
            "osm_id": random.randint(1000000, 9000000),
            "osm_type": "relation",
            "bbox": [round(lon - 0.1, 4), round(lat - 0.1, 4), round(lon + 0.1, 4), round(lat + 0.1, 4)],
            "centroid": {"lat": lat, "lon": lon},
            "has_river": has_river,
            "bridge_count": bridges,
            "road_density": round(random.uniform(0.6, 0.95), 2),
            "city_affinity_tags": ["capital", "european"] if code in ["UK", "FR", "DE", "ES", "IT"] else ["european"],
            "featured_artwork_ids": []
        }
        data["items"].append(c_item)
        existing_ids.add(cid)
        added += 1

    with open(CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Added {added} cities.")

# 2. 50 Shapes
def make_svg(points, closed=True):
    path = " ".join([f"{'M' if i==0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points)])
    if closed:
        path += " Z"
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="{path}" fill="none" stroke="black" stroke-width="2"/></svg>'

def generate_shapes():
    with open(ARTWORKS_FILE, "r", encoding="utf-8") as f:
        art_data = json.load(f)
        
    existing_ids = {a["id"] for a in art_data["items"]}
    added = 0
    
    for i in range(1, 51):
        sid = f"auto-shape-{i}"
        if sid in existing_ids:
            continue
        
        # Generate some geometric polygon
        points = []
        sides = random.randint(3, 10)
        cx, cy = 50, 50
        r = 40
        for s in range(sides):
            angle = 2 * math.pi * s / sides
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append((round(px, 1), round(py, 1)))
            
        svg_content = make_svg(points, True)
        with open(os.path.join(SHAPES_DIR, f"{sid}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_content)
            
        art_item = {
            "id": sid,
            "name": f"Geometric Shape {i}",
            "category": "geometric",
            "complexity": "easy",
            "recommended_min_km": round(random.uniform(2.0, 5.0), 1),
            "recommended_max_km": round(random.uniform(10.0, 20.0), 1),
            "aspect_ratio": 1.0,
            "closed_path": True,
            "default_sample_count": sides * 5,
            "symmetric": True,
            "tags": ["geometric", "polygon"],
            "city_affinity_tags": []
        }
        art_data["items"].append(art_item)
        added += 1

    with open(ARTWORKS_FILE, "w", encoding="utf-8") as f:
        json.dump(art_data, f, indent=2, ensure_ascii=False)
    print(f"Added {added} shapes.")

if __name__ == "__main__":
    add_cities()
    generate_shapes()
