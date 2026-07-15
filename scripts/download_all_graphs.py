import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.seed import load_cities
from app.core.osm_graph import build_osm_graph_for_city

def download_graphs():
    cities = load_cities()
    print(f"Starting graph download for {len(cities)} cities...")
    
    # Using 3 workers to not overwhelm Overpass completely, but fast enough
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(build_osm_graph_for_city, city): city for city in cities}
        
        success = 0
        for future in as_completed(futures):
            city = futures[future]
            try:
                graph = future.result()
                if graph is not None:
                    success += 1
                    print(f"Success: {city.name}")
                else:
                    print(f"Failed (returned None): {city.name}")
            except Exception as exc:
                print(f"Failed Exception: {city.name}, {exc}")
                
    print(f"Finished downloading {success}/{len(cities)} graphs.")

if __name__ == "__main__":
    download_graphs()
