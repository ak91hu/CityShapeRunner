import urllib.request
import json

req = urllib.request.Request('https://raw.githubusercontent.com/lutangar/cities.json/master/cities.json')
with urllib.request.urlopen(req) as response:
    cities = json.loads(response.read().decode('utf-8'))

hu_cities = [c for c in cities if c.get('country') == 'HU']

# Featured names to ensure
featured_names = ['Budapest', 'Debrecen', 'Szeged', 'Pécs', 'Győr', 'Veszprém', 'Siófok', 'Balatonfüred', 'Keszthely', 'Sopron', 'Eger', 'Esztergom']

# Gather top 500
final_list = []
added_names = set()

for name in featured_names:
    final_list.append(name)
    added_names.add(name.lower())

for c in hu_cities:
    name = c['name']
    if name.lower() not in added_names and not name.lower().startswith("budapest "):
        final_list.append(name)
        added_names.add(name.lower())
    if len(final_list) >= 500:
        break

items = []
for name in final_list:
    city_id = name.lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ö', 'o').replace('ő', 'o').replace('ú', 'u').replace('ü', 'u').replace('ű', 'u')
    items.append({
        'id': city_id,
        'name': name,
        'country': 'Hungary',
        'has_river': False,
        'road_density': 0.5,
        'featured_artwork_ids': [],
        'centroid': {'lat': 0.0, 'lon': 0.0}
    })

with open(r'C:\PathForge\data\seed\cities.json', 'w', encoding='utf-8') as f:
    json.dump({'items': items}, f, indent=2, ensure_ascii=False)

print(f'Saved {len(items)} cities to cities.json')
