import json
import os
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = r"C:\PathForge\data"
CITIES_FILE = os.path.join(DATA_DIR, "seed", "cities.json")
TOKEN = os.environ.get("CSR_MAPBOX_ACCESS_TOKEN")

def fetch_mapbox_data(city):
    query = f"{city['name']}, {city['country']}"
    url = f"https://api.mapbox.com/search/geocode/v6/forward?q={urllib.parse.quote(query)}&types=place&access_token={TOKEN}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get("features") and len(data["features"]) > 0:
                feature = data["features"][0]
                props = feature.get("properties", {})
                
                # Enrich with mapbox specific data
                city["mapbox_id"] = props.get("mapbox_id")
                
                # Update centroid if provided
                if "coordinates" in props:
                    city["centroid"] = {
                        "lat": props["coordinates"]["latitude"],
                        "lon": props["coordinates"]["longitude"]
                    }
                
                # Update bbox if provided
                if "bbox" in props:
                    city["bbox"] = props["bbox"]
                elif "bbox" in feature:
                    city["bbox"] = feature["bbox"]
                    
                # Add context (region, country context)
                if "context" in props:
                    city["mapbox_context"] = props["context"]
                    
                return True, city["name"], None
            else:
                return False, city["name"], "No results found"
                
    except Exception as e:
        return False, city["name"], str(e)

def enrich_cities():
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Enriching {len(data['items'])} cities...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_mapbox_data, city): city for city in data["items"]}
        
        success = 0
        for future in as_completed(futures):
            ok, name, error = future.result()
            if ok:
                success += 1
            else:
                print(f"Failed to enrich {name}: {error}")
                
    with open(CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully enriched {success}/{len(data['items'])} cities.")

if __name__ == "__main__":
    enrich_cities()
