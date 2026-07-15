import json

with open("data/seed/artworks.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for item in data["items"]:
    if "complexity" not in item:
        item["complexity"] = "medium"
    if "recommended_min_km" not in item:
        if "distance_range_km" in item:
            item["recommended_min_km"] = float(item["distance_range_km"][0])
            item["recommended_max_km"] = float(item["distance_range_km"][1])
        else:
            item["recommended_min_km"] = 5.0
            item["recommended_max_km"] = 25.0
    if "aspect_ratio" not in item:
        item["aspect_ratio"] = 1.0
    if "closed_path" not in item:
        item["closed_path"] = True
    if "default_sample_count" not in item:
        item["default_sample_count"] = 200
    if "symmetric" not in item:
        item["symmetric"] = False

with open("data/seed/artworks.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Fixed artworks.json")
