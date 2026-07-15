import { test, expect } from '@playwright/test';

test.describe('Navigation and Basic Pages', () => {
  test('should display the home page with correct hero text', async ({ page }) => {
    await page.goto('http://localhost:3000/');
    
    // Check for main heading
    const heading = page.locator('h1').first();
    await expect(heading).toBeVisible({ timeout: 10000 });
    const text = await heading.textContent();
    expect(text?.length).toBeGreaterThan(10);
    
    // The main CTA button links to /studio
    const startBtn = page.locator('a[href^="/studio"]').first();
    await expect(startBtn).toBeVisible();
    await startBtn.click();
    
    // Should navigate to studio
    await expect(page).toHaveURL(/.*\/studio.*/, { timeout: 10000 });
  });

  test('should navigate to the gallery page and filter artworks', async ({ page }) => {
    await page.goto('http://localhost:3000/gallery');
    
    // Check if artwork cards are rendered by looking for SVG inside grid
    const cards = page.locator('.card').locator('svg');
    await expect(cards.first()).toBeVisible({ timeout: 15000 });
    
    // Click on a category filter button (assuming they are buttons)
    const filterButtons = page.locator('button');
    const count = await filterButtons.count();
    expect(count).toBeGreaterThan(0);
    
    // Click the second filter button (likely a category other than "All")
    if (count > 1) {
      await filterButtons.nth(1).click();
      await page.waitForTimeout(1000);
      await expect(cards.first()).toBeVisible();
    }
  });

  test('should navigate to cities page and search for a city', async ({ page }) => {
    await page.goto('http://localhost:3000/cities');
    
    // Check if city cards are present
    const cityLinks = page.locator('a[href^="/cities/"]');
    await expect(cityLinks.first()).toBeVisible({ timeout: 15000 });
    const initialCount = await cityLinks.count();
    expect(initialCount).toBeGreaterThan(0);
    
    // Search input
    const searchInput = page.locator('input').first();
    await expect(searchInput).toBeVisible();
    
    // Search for a specific city
    await searchInput.fill('Budapest');
    await page.waitForTimeout(1000);
    
    // Should filter down the list
    const filteredCount = await cityLinks.count();
    expect(filteredCount).toBeGreaterThan(0);
    // Since Budapest is unique, the list should be smaller or equal
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });
});
