import { test, expect } from '@playwright/test';

/**
 * Health check tests - verify the app loads and basic functionality works.
 */
test.describe('Health Checks', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');
    
    // Wait for the page to be fully loaded
    await page.waitForLoadState('networkidle');
    
    // Verify the page title or main heading exists
    await expect(page).toHaveTitle(/Influencer/i);
  });

  test('search bar is visible and interactive', async ({ page }) => {
    await page.goto('/');
    
    // Look for search input or textarea
    const searchInput = page.locator('textarea, input[type="text"]').first();
    await expect(searchInput).toBeVisible();
    
    // Verify it's focusable
    await searchInput.focus();
    await expect(searchInput).toBeFocused();
  });

  test('API health endpoint responds', async ({ request }) => {
    const apiUrl = process.env.API_BASE_URL || 'http://localhost:8000';
    const response = await request.get(`${apiUrl}/health`);
    
    expect(response.ok()).toBeTruthy();
    
    const body = await response.json();
    expect(body.status).toBe('healthy');
  });
});
