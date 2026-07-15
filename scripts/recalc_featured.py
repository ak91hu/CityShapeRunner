import sys
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Add parent directory to sys.path to find the 'app' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

# Aggressive limits for much faster processing
os.environ["CSR_ENABLE_AI_RETRY"] = "false"
os.environ["CSR_MAX_CANDIDATE_TRANSFORMATIONS"] = "10"
os.environ["CSR_BEAM_WIDTH"] = "5"
os.environ["CSR_COARSE_CANDIDATE_LIMIT"] = "10"
os.environ["CSR_MEDIUM_CANDIDATE_LIMIT"] = "5"
os.environ["CSR_FINAL_CANDIDATE_LIMIT"] = "1"
os.environ["CSR_MAX_ROUTE_REPAIRS"] = "2"

from app.stores import STORE, JobRecord
from app.core.schemas import GenerationJobCreate
from app.worker import run_job

DATA_DIR = r"C:\PathForge\data"
CITIES_FILE = os.path.join(DATA_DIR, "seed", "cities.json")
ARTWORKS_FILE = os.path.join(DATA_DIR, "seed", "artworks.json")

def check_artwork_feasible(city_id, art_id, artwork_name, recommended_min_km):
    req = GenerationJobCreate(
        city_id=city_id,
        activity="running",
        target_distance_km=recommended_min_km,
        difficulty="medium",
        max_suggestions=1,
        artwork_ids=[art_id],
        force=True,
    )
    job_id = STORE.new_id("job")
    job = JobRecord(id=job_id, request=req, request_hash="mock", city_id=city_id)
    STORE.jobs[job_id] = job
    
    try:
        run_job(job_id)
    except Exception as e:
        return city_id, art_id, False, str(e)
    
    if job.status == "completed" and job.candidates:
        return city_id, art_id, True, None, job.candidates[0]
    else:
        return city_id, art_id, False, job.error_message, None

def verify_featured():
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    with open(ARTWORKS_FILE, "r", encoding="utf-8") as f:
        art_data = json.load(f)
    
    artworks = art_data["items"]
    pregenerated_candidates = []
    
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        for city in data["items"]:
            print(f"Testing all artworks for {city['name']} ({city['id']})...")
            
            future_to_art = {
                executor.submit(
                    check_artwork_feasible, 
                    city["id"], 
                    art["id"], 
                    art["name"], 
                    art.get("recommended_min_km", 10)
                ): art["id"]
                for art in artworks
            }
            
            valid_featured = []
            for future in as_completed(future_to_art):
                art_id = future_to_art[future]
                c_id, a_id, is_feasible, error, candidate = future.result()
                if is_feasible:
                    print(f"     [OK] {a_id} is feasible in {c_id}!")
                    valid_featured.append(a_id)
                    
                    # Save candidate data
                    from dataclasses import asdict
                    c_dict = asdict(candidate)
                    c_dict['scores'] = candidate.scores.model_dump(by_alias=True)
                    c_dict['city_id'] = c_id
                    c_dict['activity'] = 'running'
                    pregenerated_candidates.append(c_dict)
                    
                    # Add to city_affinity_tags
                    for art in artworks:
                        if art["id"] == a_id:
                            if "city_affinity_tags" not in art:
                                art["city_affinity_tags"] = []
                            if c_id not in art["city_affinity_tags"]:
                                art["city_affinity_tags"].append(c_id)
                            break
                else:
                    print(f"     [FAIL] {a_id} in {c_id} NOT feasible.")
                    
            city["featured_artwork_ids"] = valid_featured

    with open(CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    with open(ARTWORKS_FILE, "w", encoding="utf-8") as f:
        json.dump(art_data, f, indent=2)
        
    PREGEN_FILE = os.path.join(DATA_DIR, "seed", "pregenerated_candidates.json")
    with open(PREGEN_FILE, "w", encoding="utf-8") as f:
        json.dump(pregenerated_candidates, f, indent=2)
        
    print("Verification complete. Updated cities.json, artworks.json and pregenerated_candidates.json.")

if __name__ == "__main__":
    verify_featured()
