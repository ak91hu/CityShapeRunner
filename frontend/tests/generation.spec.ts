import { test, expect } from '@playwright/test';

test.describe('Shape Generation UI', () => {
  test('should select a shape, a city, generate a route, and verify it renders successfully', async ({ page }) => {
    test.setTimeout(60000); // Allow up to 2 minutes for the entire test
    page.on('console', msg => console.log('Browser:', msg.text()));
    page.on('response', resp => { if(resp.url().includes('/api/')) console.log('API Response:', resp.url(), resp.status()); });

    // 1. Open the studio page
    await page.goto('http://localhost:3000/studio');

    // 2. Select the first available shape (wait for API to load them first)
    const shapeBtn = page.getByTestId('shape-button').first();
    await shapeBtn.waitFor({ state: 'visible', timeout: 10000 });

    await expect(async () => {
      if (await shapeBtn.isVisible()) {
        await shapeBtn.click();
      }
      await expect(shapeBtn).toBeHidden({ timeout: 1000 });
    }).toPass({ timeout: 15000 });

    const html = await page.content();
    require('fs').writeFileSync('debug.html', html);

    // 3. Select the first compatible city (wait for list to load)
    const cityBtn = page.getByTestId('city-button').first();
    await cityBtn.waitFor({ state: 'visible', timeout: 30000 });
    await cityBtn.click();

    // 4. Click generate
    const generateButton = page.locator('button', { hasText: /Útvonal generálása|Generate route/i });
    await generateButton.waitFor({ state: 'visible' });
    await expect(generateButton).toBeEnabled({ timeout: 30000 });
    await generateButton.click();

    // 5. Wait for the generation animation
    const generatingText = page.locator('h3', { hasText: /Generálás|Generating/i });
    // Since generating can be very fast, it might not be visible, so we don't strictly require it to be visible for 5s,
    // but we can try to wait for it. If it fails, maybe it already finished.
    // Instead of failing the test, let's just wait for the map directly.
    
    // 6. Wait for the generated map to appear
    // The RouteMap component renders a Leaflet map container
    const mapContainer = page.locator('.leaflet-container');
    // Wait up to 60 seconds for the backend to finish processing
    await mapContainer.waitFor({ state: 'visible', timeout: 60000 });

    // 7. Verify that the generated shape renders as a polyline (SVG path) inside the map
    const svgPath = mapContainer.locator('svg path.leaflet-interactive').first();
    await expect(svgPath).toBeVisible();

    // Ensure the path has a significant "d" attribute representing the shape
    const dAttribute = await svgPath.getAttribute('d');
    expect(dAttribute).toBeTruthy();
    expect(dAttribute?.length).toBeGreaterThan(50); // a real shape has many points
  });
});
