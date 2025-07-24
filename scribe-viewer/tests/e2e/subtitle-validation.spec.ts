import { test, expect } from '@playwright/test';

// Test interview ID that was used for validation
const TEST_INTERVIEW_ID = '25af0f9c-8f96-44c9-be5e-e92cb462a41f';

test.describe('Subtitle System Validation', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the interview viewer
    await page.goto(`/interviews/${TEST_INTERVIEW_ID}`);
    
    // Wait for video player to load
    await page.waitForSelector('video', { timeout: 10000 });
  });

  test('should display all language options including original', async ({ page }) => {
    // Click on subtitle button
    const subtitleButton = page.locator('button[aria-label*="Subtitles"]');
    await subtitleButton.click();
    
    // Check that all language options are available
    await expect(page.locator('text=Original')).toBeVisible();
    await expect(page.locator('text=English')).toBeVisible();
    await expect(page.locator('text=German')).toBeVisible();
    await expect(page.locator('text=Hebrew')).toBeVisible();
  });

  test('should maintain timing synchronization', async ({ page }) => {
    // Enable German subtitles
    const subtitleButton = page.locator('button[aria-label*="Subtitles"]');
    await subtitleButton.click();
    await page.locator('text=German').click();
    
    // Get video element
    const video = page.locator('video');
    
    // Seek to specific timestamp where we validated the translation
    await video.evaluate((el: HTMLVideoElement) => {
      el.currentTime = 2382.03; // 00:39:42.030
    });
    
    // Wait for subtitle to appear
    await page.waitForTimeout(500);
    
    // Check that subtitle is displayed at correct time
    const subtitle = page.locator('.subtitle-text');
    await expect(subtitle).toBeVisible();
  });

  test('should show German translation for English segments', async ({ page }) => {
    // Enable German subtitles
    const subtitleButton = page.locator('button[aria-label*="Subtitles"]');
    await subtitleButton.click();
    await page.locator('text=German').click();
    
    // Seek to the English segment that should be translated
    const video = page.locator('video');
    await video.evaluate((el: HTMLVideoElement) => {
      el.currentTime = 2382.03; // 00:39:42.030 - "much Jews. We know that one"
    });
    
    // Wait for subtitle
    await page.waitForTimeout(500);
    
    // Verify German translation appears
    const subtitle = page.locator('.subtitle-text');
    const text = await subtitle.textContent();
    
    // Should contain German translation, not English
    expect(text).toContain('viele Juden');
    expect(text).not.toContain('much Jews');
  });

  test('should preserve German segments when target is German', async ({ page }) => {
    // Enable German subtitles
    const subtitleButton = page.locator('button[aria-label*="Subtitles"]');
    await subtitleButton.click();
    await page.locator('text=German').click();
    
    // Seek to a German segment
    const video = page.locator('video');
    await video.evaluate((el: HTMLVideoElement) => {
      el.currentTime = 60; // Early in the interview - likely German
    });
    
    // Wait and check subtitle
    await page.waitForTimeout(500);
    
    // Get original subtitles for comparison
    await subtitleButton.click();
    await page.locator('text=Original').click();
    await page.waitForTimeout(500);
    const originalText = await page.locator('.subtitle-text').textContent();
    
    // Switch back to German
    await subtitleButton.click();
    await page.locator('text=German').click();
    await page.waitForTimeout(500);
    const germanText = await page.locator('.subtitle-text').textContent();
    
    // If original was German, it should be preserved
    if (originalText && /[äöüßÄÖÜ]/.test(originalText)) {
      expect(germanText).toBe(originalText);
    }
  });

  test('should load subtitles without errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // Try loading each subtitle language
    const languages = ['Original', 'English', 'German', 'Hebrew'];
    
    for (const lang of languages) {
      const subtitleButton = page.locator('button[aria-label*="Subtitles"]');
      await subtitleButton.click();
      await page.locator(`text=${lang}`).click();
      await page.waitForTimeout(1000);
    }
    
    // Check no subtitle-related errors
    const subtitleErrors = consoleErrors.filter(err => 
      err.includes('subtitle') || err.includes('vtt') || err.includes('track')
    );
    
    expect(subtitleErrors).toHaveLength(0);
  });

  test('should have all subtitle files accessible', async ({ page }) => {
    // Check that all subtitle files return 200 status
    const subtitleUrls = [
      `/subtitles/${TEST_INTERVIEW_ID}.orig.vtt`,
      `/subtitles/${TEST_INTERVIEW_ID}.en.vtt`,
      `/subtitles/${TEST_INTERVIEW_ID}.de.vtt`,
      `/subtitles/${TEST_INTERVIEW_ID}.he.vtt`
    ];
    
    for (const url of subtitleUrls) {
      const response = await page.request.get(url);
      expect(response.status()).toBe(200);
      
      const content = await response.text();
      expect(content).toContain('WEBVTT');
      expect(content.length).toBeGreaterThan(100); // Not empty
    }
  });
});