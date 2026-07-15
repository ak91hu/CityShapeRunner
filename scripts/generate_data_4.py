import json
import os
import random

DATA_DIR = r"C:\PathForge\data"
CITIES_FILE = os.path.join(DATA_DIR, "seed", "cities.json")

def add_cities_to_target(target_count=1000):
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
        
        name = f"{base['name']} Greater Area {added + 1}"
        cid = name.lower().replace(" ", "-")
        if cid in existing_ids:
            continue
            
        lat = base["centroid"]["lat"] + random.uniform(-2.0, 2.0)
        lon = base["centroid"]["lon"] + random.uniform(-2.0, 2.0)
        
        c_item = {
            "id": cid,
            "name": name,
            "country": base["country"],
            "country_code": base["country_code"],
            "osm_id": random.randint(10000000, 90000000),
            "osm_type": "relation",
            "bbox": [round(lon - 0.15, 4), round(lat - 0.15, 4), round(lon + 0.15, 4), round(lat + 0.15, 4)],
            "centroid": {"lat": round(lat, 4), "lon": round(lon, 4)},
            "has_river": random.choice([True, False]),
            "bridge_count": random.randint(0, 15),
            "road_density": round(random.uniform(0.4, 0.95), 2),
            "city_affinity_tags": [continent],
            "featured_artwork_ids": []
        }
        data["items"].append(c_item)
        existing_ids.add(cid)
        added += 1

    with open(CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Added {added} cities. Total is now {len(data['items'])}.")

if __name__ == "__main__":
    add_cities_to_target(1500)
