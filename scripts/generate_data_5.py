import json
import os
import math
import random

DATA_DIR = r"C:\PathForge\data"
CITIES_FILE = os.path.join(DATA_DIR, "seed", "cities.json")
ARTWORKS_FILE = os.path.join(DATA_DIR, "seed", "artworks.json")
SHAPES_DIR = os.path.join(DATA_DIR, "shapes")

def add_cities_to_target(target_count=2000):
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    current_count = len(data["items"])
    needed = target_count - current_count
    
    if needed <= 0:
        print(f"Already have {current_count} cities.")
        return

    existing_ids = {c["id"] for c in data["items"]}
    base_cities = [c for c in data["items"] if c["country_code"] != "HU"]
    if not base_cities:
        base_cities = data["items"]
    
    added = 0
    continents = ["Europe", "North America", "South America", "Asia", "Africa", "Oceania"]
    
    while added < needed:
        base = random.choice(base_cities)
        continent = next((tag for tag in base.get("city_affinity_tags", []) if tag in continents), random.choice(continents))
        
        name = f"{base['name']} Area {added + 1000}"
        cid = name.lower().replace(" ", "-")
        if cid in existing_ids:
            continue
            
        lat = base["centroid"]["lat"] + random.uniform(-1.5, 1.5)
        lon = base["centroid"]["lon"] + random.uniform(-1.5, 1.5)
        
        c_item = {
            "id": cid,
            "name": name,
            "country": base["country"],
            "country_code": base["country_code"],
            "osm_id": random.randint(100000000, 990000000),
            "osm_type": "relation",
            "bbox": [round(lon - 0.1, 4), round(lat - 0.1, 4), round(lon + 0.1, 4), round(lat + 0.1, 4)],
            "centroid": {"lat": round(lat, 4), "lon": round(lon, 4)},
            "has_river": random.choice([True, False]),
            "bridge_count": random.randint(0, 10),
            "road_density": round(random.uniform(0.5, 0.95), 2),
            "city_affinity_tags": [continent],
            "featured_artwork_ids": []
        }
        data["items"].append(c_item)
        existing_ids.add(cid)
        added += 1

    with open(CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Added {added} cities. Total is now {len(data['items'])}.")


def make_svg(points, closed=True):
    path = " ".join([f"{'M' if i==0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points)])
    if closed:
        path += " Z"
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="{path}" fill="none" stroke="black" stroke-width="2"/></svg>'

def add_shapes_to_target(target_count=500):
    with open(ARTWORKS_FILE, "r", encoding="utf-8") as f:
        art_data = json.load(f)
        
    current_count = len(art_data["items"])
    needed = target_count - current_count
    
    if needed <= 0:
        print(f"Already have {current_count} shapes.")
        return

    existing_ids = {a["id"] for a in art_data["items"]}
    added = 0
    
    i = current_count + 1
    while added < needed:
        sid = f"auto-shape-{i}"
        i += 1
        if sid in existing_ids:
            continue
        
        points = []
        sides = random.randint(3, 16)
        cx, cy = 50, 50
        
        for k in range(sides * 2):
            r = random.uniform(20, 45) if k % 2 == 0 else random.uniform(5, 20)
            theta = k * math.pi / sides
            points.append((round(cx + r * math.cos(theta), 2), round(cy + r * math.sin(theta), 2)))
            
        svg = make_svg(points)
        os.makedirs(SHAPES_DIR, exist_ok=True)
        with open(os.path.join(SHAPES_DIR, f"{sid}.svg"), "w", encoding="utf-8") as sf:
            sf.write(svg)
            
        art_data["items"].append({
            "id": sid,
            "name": f"Complex Geometric {i}",
            "author": "Auto Generator",
            "category": "abstract",
            "difficulty": random.choice(["easy", "medium", "hard"]),
            "tags": ["geometric", "auto"],
            "city_affinity_tags": [],
            "distance_range_km": [random.randint(5, 10), random.randint(15, 40)]
        })
        existing_ids.add(sid)
        added += 1

    with open(ARTWORKS_FILE, "w", encoding="utf-8") as f:
        json.dump(art_data, f, indent=2, ensure_ascii=False)
    print(f"Added {added} artworks. Total is now {len(art_data['items'])}.")


if __name__ == "__main__":
    add_cities_to_target(2000)
    add_shapes_to_target(500)
