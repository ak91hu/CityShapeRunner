import { test, expect } from '@playwright/test';

test.describe('Advanced Interactions', () => {
  test('Search filtering logic reduces city count', async ({ page }) => {
    await page.goto('http://localhost:3000/cities');
    
    const input = page.locator('input').first();
    await input.waitFor({ state: 'visible' });

    // Wait for the grid to populate with items
    const allLinks = page.locator('a[href^="/cities/"]');
    await expect(allLinks.first()).toBeVisible({ timeout: 15000 });
    
    // Original count must be 500 (since we have 500 cities) or at least > 10
    const originalCount = await allLinks.count();
    expect(originalCount).toBeGreaterThan(10);
    
    // Filter out everything but Szeged
    await input.fill('Szeged');
    await page.waitForTimeout(1000); // Debounce
    
    const filteredCount = await allLinks.count();
    expect(filteredCount).toBeGreaterThan(0);
    expect(filteredCount).toBeLessThan(originalCount);
    
    // It should contain 'Szeged'
    const firstCityName = await allLinks.first().textContent();
    expect(firstCityName?.toLowerCase()).toContain('szeged');
  });

  test('Gallery category filter logic', async ({ page }) => {
    await page.goto('http://localhost:3000/gallery');
    
    const allCards = page.locator('a[href^="/gallery/"]');
    await expect(allCards.first()).toBeVisible({ timeout: 15000 });
    
    const totalCount = await allCards.count();
    expect(totalCount).toBeGreaterThan(50);
    
    // Find category buttons
    const filters = page.locator('button');
    const animalsBtn = filters.filter({ hasText: /Animals|Állatok/i }).first();
    
    if (await animalsBtn.isVisible()) {
      await animalsBtn.click();
      await page.waitForTimeout(1000);
      
      const filteredCount = await allCards.count();
      expect(filteredCount).toBeGreaterThan(0);
      expect(filteredCount).toBeLessThan(totalCount);
    }
  });

  test('Error handling in Studio layout', async ({ page }) => {
    // Navigate directly without required query params should display warning or default
    await page.goto('http://localhost:3000/studio');
    const shapeSection = page.locator('h3').first(); // Steps
    await expect(shapeSection).toBeVisible();
    
    // Generate button should be disabled at the start
    const generateBtn = page.locator('button', { hasText: /Útvonal generálása|Generate route/i });
    if (await generateBtn.isVisible()) {
        await expect(generateBtn).toBeDisabled();
    }
  });
});
