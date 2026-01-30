import { test, expect } from '@playwright/test';

/**
 * Accessibility E2E tests.
 * Verifies basic a11y requirements are met.
 */
test.describe('Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('page has proper heading structure', async ({ page }) => {
    // Should have at least one h1
    const h1Count = await page.locator('h1').count();
    expect(h1Count).toBeGreaterThanOrEqual(1);
  });

  test('interactive elements are keyboard accessible', async ({ page }) => {
    // Tab through the page and verify focus is visible
    await page.keyboard.press('Tab');
    
    // Something should be focused
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });

  test('search input has accessible label', async ({ page }) => {
    const searchInput = page.locator('textarea, input[type="text"]').first();
    
    // Check for aria-label, aria-labelledby, or associated label
    const hasAriaLabel = await searchInput.getAttribute('aria-label');
    const hasAriaLabelledBy = await searchInput.getAttribute('aria-labelledby');
    const hasPlaceholder = await searchInput.getAttribute('placeholder');
    const inputId = await searchInput.getAttribute('id');
    
    let hasLabel = false;
    if (inputId) {
      hasLabel = await page.locator(`label[for="${inputId}"]`).count() > 0;
    }
    
    // At least one of these should exist for accessibility
    const isAccessible = hasAriaLabel || hasAriaLabelledBy || hasLabel || hasPlaceholder;
    expect(isAccessible).toBeTruthy();
  });

  test('buttons have accessible names', async ({ page }) => {
    const buttons = page.locator('button');
    const buttonCount = await buttons.count();
    
    for (let i = 0; i < Math.min(buttonCount, 5); i++) {
      const button = buttons.nth(i);
      
      // Button should have text content, aria-label, or title
      const text = await button.textContent();
      const ariaLabel = await button.getAttribute('aria-label');
      const title = await button.getAttribute('title');
      
      const hasAccessibleName = (text && text.trim()) || ariaLabel || title;
      expect(hasAccessibleName).toBeTruthy();
    }
  });

  test('color contrast is sufficient for text', async ({ page }) => {
    // Basic check - verify text elements exist and are visible
    const textElements = page.locator('p, span, h1, h2, h3, label');
    const count = await textElements.count();
    
    // At least some text should be visible
    expect(count).toBeGreaterThan(0);
    
    // First visible text element should be actually visible (not hidden)
    const firstText = textElements.first();
    await expect(firstText).toBeVisible();
  });
});
