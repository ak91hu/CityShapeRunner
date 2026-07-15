# Skill: Add a New City

This workflow outlines the steps required to introduce a new playable city into the CityShapeRunner (PathForge) environment.

## 1. Extract and Add the Seed City Data
1. Find the geographic centroid (latitude, longitude) of the city.
2. Ensure the city is supported by OpenStreetMap / Overpass.
3. Update `app/core/seed.py`:
   - Add the new city to the `list_all_cities()` or the predefined data structures.
   - Define its bounding box (`bbox`), name, country, and `osm_id` / `osm_type` (relation).

## 2. Run Data Generation (Optional but Recommended)
For production, the graphs are built dynamically via OSMNx. However, to pre-generate fixtures or test datasets:
- Run `python scripts/generate_data.py` (adjusting the script if necessary) to export the road graph to a local file in `data/cities/`.

## 3. Configure Artworks
- Check if the city needs any exclusive artworks (e.g. `featured_artwork_ids` in `seed.py`).

## 4. Test
- Start the server: `python -m app.main`
- Request `GET /api/cities/{city_id}` to verify data format.
- Run a generation job for the new city to ensure OSM graph extraction works without timing out or missing crucial roads.
