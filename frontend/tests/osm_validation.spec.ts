import { test, expect } from '@playwright/test';

// UI teszt: Ellenőrzi, hogy a generált alakzat valódi (OSM) utakon halad-e, és felismerhető-e.
test.describe('Shape Routing and Recognition Check', () => {
  test('Generated shape should follow real OSM paths and be recognizable', async ({ page, request }) => {
    test.setTimeout(300000); // 5 perc a generálásra és hálózati kérésekre

    // Figyeljük a generálási job végét jelző hálózati választ
    const jobCompletedPromise = page.waitForResponse(async response => {
      if (response.url().includes('/api/generation/jobs/job_') && response.request().method() === 'GET') {
        const json = await response.json().catch(() => ({}));
        return json.status === 'completed';
      }
      return false;
    }, { timeout: 280000 });

    await page.goto('http://localhost:3000/studio');
    
    // Alakzat kiválasztása
    const shapeBtn = page.getByTestId('shape-button').first();
    await shapeBtn.waitFor({ state: 'visible', timeout: 30000 });
    await shapeBtn.click();
    
    // Város kiválasztása
    const cityBtn = page.getByTestId('city-button').first();
    await cityBtn.waitFor({ state: 'visible', timeout: 30000 });
    await cityBtn.click();
    
    // Generálás indítása - ez a backend-en kiváltja az ORS API lekéréseket
    const generateButton = page.locator('button', { hasText: /Útvonal generálása|Generate route/i });
    await generateButton.waitFor({ state: 'visible' });
    await expect(generateButton).toBeEnabled();
    await generateButton.click();
    
    // Várjuk meg a backend válaszát
    const response = await jobCompletedPromise;
    const data = await response.json();
    
    expect(data.suggestions.length).toBeGreaterThan(0);
    const candidate = data.suggestions[0];

    // 1. ALAKZAT FELISMERHETŐSÉGÉNEK ELLENŐRZÉSE
    // A shape_similarity_score adja meg, hogy mennyire hasonlít az eredetihez.
    console.log(`Shape similarity score: ${candidate.scores.shape_similarity_score}`);
    expect(candidate.scores.shape_similarity_score).toBeGreaterThan(0.50);
    
    // 2. VALÓS UTAK (ORS) HASZNÁLATÁNAK ELLENŐRZÉSE OSM ADATOKKAL
    // Lekérjük a GeoJSON-t, ami az ORS által visszaadott pontos útvonalat tartalmazza
    const geoJsonUrl = candidate.preview_geo_json_url.startsWith('http') 
        ? candidate.preview_geo_json_url 
        : 'http://localhost:8001' + candidate.preview_geo_json_url;
        
    const geoJsonResponse = await request.get(geoJsonUrl);
    const geoJson = await geoJsonResponse.json();
    
    const coords = geoJson.features[0].geometry.coordinates; // [lon, lat] tömb
    expect(coords.length).toBeGreaterThan(10); // Az igazi ORS útvonalak sok pontból állnak
    
    // Bounding box kiszámítása az Overpass lekéréshez
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    for (const [lon, lat] of coords) {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
    }
    
    // Kis buffer (kb. 500m)
    minLon -= 0.005; maxLon += 0.005;
    minLat -= 0.005; maxLat += 0.005;
    
    // Overpass API lekérés az adott bounding boxra
    const overpassQuery = `
      [out:json];
      way["highway"](${minLat},${minLon},${maxLat},${maxLon});
      out geom;
    `;
    
    console.log("Fetching OSM data via Overpass API...");
    const overpassRes = await request.post('https://overpass-api.de/api/interpreter', {
        data: overpassQuery,
        headers: { 'Content-Type': 'text/plain' }
    });
    
    const osmData = await overpassRes.json();
    expect(osmData.elements).toBeDefined();
    expect(osmData.elements.length).toBeGreaterThan(0);
    
    // Ellenőrizzük, hogy az útvonal pontjai rajta vannak-e az OSM utakon
    let pointsOnRoad = 0;
    for (const [lon, lat] of coords) {
       let minD = 999999;
       for (const el of osmData.elements) {
           if (!el.geometry) continue;
           for (const nd of el.geometry) {
               // Pitagorasz-tétel fokokban (csak közelítés, de erre a célra elég)
               const d = Math.sqrt(Math.pow(nd.lon - lon, 2) + Math.pow(nd.lat - lat, 2));
               if (d < minD) minD = d;
           }
       }
       // 0.0005 fok nagyjából 50 méter
       if (minD < 0.0005) {
           pointsOnRoad++;
       }
    }
    
    const onRoadRatio = pointsOnRoad / coords.length;
    console.log(`Pontok aránya, amik rajta vannak az OSM utakon: ${(onRoadRatio * 100).toFixed(2)}%`);
    
    // Elvárjuk, hogy a pontok nagy része valós OSM utakon haladjon (amit az ORS intézett)
    expect(onRoadRatio).toBeGreaterThan(0.70);
  });
});
