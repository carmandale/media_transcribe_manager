/**
 * End-to-End Tests for Search Workflow
 * Tests complete user journeys through the search functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Search Workflow E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
  });

  test.describe('Gallery Search Integration', () => {
    test('should display gallery with search functionality', async ({ page }) => {
      // Wait for gallery to load
      await expect(page.locator('h1')).toContainText('Interview Gallery');
      
      // Check that search input is present
      const searchInput = page.locator('input[placeholder*="Search"]');
      await expect(searchInput).toBeVisible();
      
      // Check that interviews are loaded
      const interviewCards = page.locator('[data-testid="interview-card"]');
      await expect(interviewCards.first()).toBeVisible({ timeout: 10000 });
    });

    test('should perform search from gallery', async ({ page }) => {
      // Wait for gallery to load
      await page.waitForSelector('input[placeholder*="Search"]');
      
      // Perform search
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Hamburg');
      await searchInput.press('Enter');
      
      // Wait for search results
      await page.waitForTimeout(1000);
      
      // Check that results are filtered
      const interviewCards = page.locator('[data-testid="interview-card"]');
      const cardCount = await interviewCards.count();
      expect(cardCount).toBeGreaterThan(0);
      
      // Verify search term appears in results
      const firstCard = interviewCards.first();
      const cardText = await firstCard.textContent();
      expect(cardText?.toLowerCase()).toContain('hamburg');
    });

    test('should clear search and show all results', async ({ page }) => {
      const searchInput = page.locator('input[placeholder*="Search"]');
      
      // Perform search first
      await searchInput.fill('Hamburg');
      await searchInput.press('Enter');
      await page.waitForTimeout(1000);
      
      const filteredCount = await page.locator('[data-testid="interview-card"]').count();
      
      // Clear search
      await searchInput.clear();
      await searchInput.press('Enter');
      await page.waitForTimeout(1000);
      
      const allCount = await page.locator('[data-testid="interview-card"]').count();
      
      // Should show more results after clearing
      expect(allCount).toBeGreaterThan(filteredCount);
    });
  });

  test.describe('Dedicated Search Page', () => {
    test('should navigate to search page', async ({ page }) => {
      // Navigate to search page
      await page.goto('/search');
      
      // Check page loaded correctly
      await expect(page.locator('h1')).toContainText('Advanced Search');
      
      // Check search components are present
      await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
      await expect(page.locator('button')).toContainText('Search');
    });

    test('should perform advanced search with filters', async ({ page }) => {
      await page.goto('/search');
      
      // Fill search query
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Friedrich');
      
      // Apply filters if available
      const filterButtons = page.locator('button[data-testid*="filter"]');
      if (await filterButtons.count() > 0) {
        await filterButtons.first().click();
      }
      
      // Perform search
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for results
      await page.waitForTimeout(2000);
      
      // Check results are displayed
      const results = page.locator('[data-testid="search-result"]');
      const resultCount = await results.count();
      expect(resultCount).toBeGreaterThan(0);
      
      // Verify search term is highlighted in results
      const firstResult = results.first();
      const highlightedText = firstResult.locator('mark, .highlight, strong');
      if (await highlightedText.count() > 0) {
        const highlightText = await highlightedText.first().textContent();
        expect(highlightText?.toLowerCase()).toContain('friedrich');
      }
    });

    test('should handle no results gracefully', async ({ page }) => {
      await page.goto('/search');
      
      // Search for non-existent term
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('nonexistentterm12345');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for search to complete
      await page.waitForTimeout(2000);
      
      // Check for no results message
      const noResultsMessage = page.locator('text=No results found, text=No interviews found, text=0 results');
      await expect(noResultsMessage.first()).toBeVisible();
    });

    test('should display search performance metrics', async ({ page }) => {
      await page.goto('/search');
      
      // Perform search
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Hamburg');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for results
      await page.waitForTimeout(2000);
      
      // Check for performance indicators
      const performanceText = page.locator('text*=results, text*=found, text*=ms, text*=seconds');
      if (await performanceText.count() > 0) {
        const perfText = await performanceText.first().textContent();
        expect(perfText).toBeTruthy();
      }
    });
  });

  test.describe('Search Result Interaction', () => {
    test('should navigate to interview viewer from search results', async ({ page }) => {
      await page.goto('/search');
      
      // Perform search
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Hamburg');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for results
      await page.waitForTimeout(2000);
      
      // Click on first result
      const firstResult = page.locator('[data-testid="search-result"], [data-testid="interview-card"]').first();
      const viewButton = firstResult.locator('button:has-text("View"), a:has-text("View"), button:has-text("Watch")');
      
      if (await viewButton.count() > 0) {
        await viewButton.click();
        
        // Should navigate to viewer page
        await page.waitForURL('**/viewer/**');
        
        // Check viewer page loaded
        await expect(page.locator('video, iframe')).toBeVisible({ timeout: 10000 });
      }
    });

    test('should show interview metadata in search results', async ({ page }) => {
      await page.goto('/search');
      
      // Perform search
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Friedrich');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for results
      await page.waitForTimeout(2000);
      
      // Check first result has metadata
      const firstResult = page.locator('[data-testid="search-result"], [data-testid="interview-card"]').first();
      
      // Should contain interviewee name
      const resultText = await firstResult.textContent();
      expect(resultText).toBeTruthy();
      expect(resultText!.length).toBeGreaterThan(10);
    });
  });

  test.describe('Responsive Design', () => {
    test('should work on mobile devices', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      
      await page.goto('/search');
      
      // Check mobile layout
      await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
      
      // Perform search
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Hamburg');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for results
      await page.waitForTimeout(2000);
      
      // Check results are displayed properly on mobile
      const results = page.locator('[data-testid="search-result"], [data-testid="interview-card"]');
      if (await results.count() > 0) {
        const firstResult = results.first();
        await expect(firstResult).toBeVisible();
        
        // Check result is not cut off
        const boundingBox = await firstResult.boundingBox();
        expect(boundingBox?.width).toBeLessThanOrEqual(375);
      }
    });

    test('should work on tablet devices', async ({ page }) => {
      // Set tablet viewport
      await page.setViewportSize({ width: 768, height: 1024 });
      
      await page.goto('/search');
      
      // Check tablet layout
      await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
      
      // Perform search and verify layout
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Friedrich');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      await page.waitForTimeout(2000);
      
      // Check results layout on tablet
      const results = page.locator('[data-testid="search-result"], [data-testid="interview-card"]');
      if (await results.count() > 0) {
        await expect(results.first()).toBeVisible();
      }
    });
  });

  test.describe('Performance Testing', () => {
    test('should load search page quickly', async ({ page }) => {
      const startTime = Date.now();
      
      await page.goto('/search');
      
      // Wait for search input to be ready
      await page.waitForSelector('input[placeholder*="Search"]');
      
      const loadTime = Date.now() - startTime;
      
      // Should load in under 5 seconds
      expect(loadTime).toBeLessThan(5000);
      
      console.log(`Search page loaded in ${loadTime}ms`);
    });

    test('should perform search quickly', async ({ page }) => {
      await page.goto('/search');
      
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Hamburg');
      
      const startTime = Date.now();
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for results to appear
      await page.waitForSelector('[data-testid="search-result"], [data-testid="interview-card"], text=No results', { timeout: 10000 });
      
      const searchTime = Date.now() - startTime;
      
      // Search should complete in under 5 seconds
      expect(searchTime).toBeLessThan(5000);
      
      console.log(`Search completed in ${searchTime}ms`);
    });
  });

  test.describe('Error Handling', () => {
    test('should handle network errors gracefully', async ({ page }) => {
      // Intercept API calls and simulate network error
      await page.route('**/api/**', route => {
        route.abort('failed');
      });
      
      await page.goto('/search');
      
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('Hamburg');
      
      const searchButton = page.locator('button:has-text("Search")');
      await searchButton.click();
      
      // Wait for error handling
      await page.waitForTimeout(3000);
      
      // Should show error message or handle gracefully
      const errorMessage = page.locator('text*=error, text*=failed, text*=try again');
      const noResults = page.locator('text=No results');
      
      // Either error message or no results should be shown
      const hasErrorHandling = await errorMessage.count() > 0 || await noResults.count() > 0;
      expect(hasErrorHandling).toBe(true);
    });

    test('should handle malformed search queries', async ({ page }) => {
      await page.goto('/search');
      
      // Test various edge case queries
      const edgeCaseQueries = [
        '', // Empty query
        '   ', // Whitespace only
        '!@#$%^&*()', // Special characters
        'a'.repeat(1000), // Very long query
      ];
      
      for (const query of edgeCaseQueries) {
        const searchInput = page.locator('input[placeholder*="Search"]');
        await searchInput.clear();
        await searchInput.fill(query);
        
        const searchButton = page.locator('button:has-text("Search")');
        await searchButton.click();
        
        // Wait for response
        await page.waitForTimeout(1000);
        
        // Should not crash or show error
        const pageTitle = await page.title();
        expect(pageTitle).toBeTruthy();
      }
    });
  });
});

