import { test, expect } from '@playwright/test';

test.describe('API Endpoint Tests', () => {
  const API_URL = 'http://localhost:8000/api';

  test('GET /api/health should return ok', async ({ request }) => {
    const response = await request.get(`${API_URL}/health`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBe('ok');
    expect(data.version).toBeDefined();
  });

  test('GET /api/cities should return a list of cities', async ({ request }) => {
    const response = await request.get(`${API_URL}/cities`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    const cities = data.items;
    expect(Array.isArray(cities)).toBeTruthy();
    expect(cities.length).toBeGreaterThan(0);
    expect(cities[0].id).toBeDefined();
    expect(cities[0].name).toBeDefined();
  });

  test('GET /api/artworks should return a list of artworks', async ({ request }) => {
    const response = await request.get(`${API_URL}/artworks`);
    expect(response.ok()).toBeTruthy();
    const data2 = await response.json();
    const artworks = data2.items;
    expect(Array.isArray(artworks)).toBeTruthy();
    expect(artworks.length).toBeGreaterThan(0);
    expect(artworks[0].id).toBeDefined();
    expect(artworks[0].name).toBeDefined();
    expect(artworks[0].category).toBeDefined();
  });

  test('POST /api/generation/jobs should reject invalid requests', async ({ request }) => {
    const response = await request.post(`${API_URL}/generation/jobs`, {
      data: {
        cityId: 'invalid-city',
        artworkId: 'invalid-artwork',
        activity: 'running',
        targetDistanceKm: 5.0
      }
    });
    // Fastapi returns 422 or 404 for invalid data
    expect(response.status()).toBeGreaterThanOrEqual(400);
  });
});
