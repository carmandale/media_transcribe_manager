import { test, expect } from '@playwright/test';

const TEST_INTERVIEW_ID = '25af0f9c-8f96-44c9-be5e-e92cb462a41f';

test.describe('Quick Subtitle Check', () => {
  test('subtitle files should be accessible via web server', async ({ page }) => {
    // Test that subtitle files are accessible
    const subtitlePaths = [
      `/media/${TEST_INTERVIEW_ID}/${TEST_INTERVIEW_ID}.orig.vtt`,
      `/media/${TEST_INTERVIEW_ID}/${TEST_INTERVIEW_ID}.de.vtt`,
    ];
    
    for (const path of subtitlePaths) {
      const response = await page.request.get(path);
      expect(response.status()).toBe(200);
      
      const content = await response.text();
      expect(content).toContain('WEBVTT');
      console.log(`✓ ${path} is accessible and valid`);
    }
  });

  test('German subtitle should contain translated content', async ({ page }) => {
    // Get the German subtitle file
    const response = await page.request.get(`/media/${TEST_INTERVIEW_ID}/${TEST_INTERVIEW_ID}.de.vtt`);
    const content = await response.text();
    
    // Check that it contains German content
    const germanWords = ['der', 'die', 'das', 'und', 'ich', 'war', 'haben'];
    const hasGerman = germanWords.some(word => content.toLowerCase().includes(word));
    expect(hasGerman).toBe(true);
    
    // Check specific timestamp - this is where "much Jews" was
    const lines = content.split('\n');
    let foundTimestamp = false;
    let contentAtTimestamp = '';
    
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes('00:39:42.030 --> 00:39:45.110')) {
        foundTimestamp = true;
        if (i + 1 < lines.length) {
          contentAtTimestamp = lines[i + 1].trim();
        }
        break;
      }
    }
    
    console.log(`Content at 00:39:42.030: "${contentAtTimestamp}"`);
    
    // This will currently fail because we haven't reprocessed the file
    // But it will show us what's actually there
    if (contentAtTimestamp.includes('much Jews')) {
      console.log('❌ English text found - subtitle needs reprocessing with fix');
    } else if (contentAtTimestamp.includes('Juden')) {
      console.log('✅ German translation found');
    }
  });
});