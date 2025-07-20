/**
 * Edge Case and Error Handling Tests
 * Tests system behavior with malformed data, missing files, and error conditions
 */

import { getSearchEngine } from '@/lib/search';
import { Interview } from '@/lib/types';

describe('Edge Case and Error Handling Tests', () => {
  describe('Malformed Data Handling', () => {
    test('should handle empty interview array', () => {
      const emptyInterviews: Interview[] = [];
      const searchEngine = getSearchEngine(emptyInterviews);
      
      const results = searchEngine.search('test');
      expect(results).toEqual([]);
      
      const filterOptions = searchEngine.getFilterOptions();
      expect(filterOptions.interviewees).toEqual([]);
      expect(filterOptions.languages).toEqual([]);
    });

    test('should handle interviews with missing metadata', () => {
      const malformedInterviews = [
        {
          id: '1',
          metadata: {
            interviewee: 'Test Person',
            summary: 'Test summary',
          },
        },
        {
          id: '2',
          // @ts-ignore - Intentionally missing metadata for testing
          metadata: null,
        },
        {
          id: '3',
          metadata: {
            interviewee: '',
            summary: '',
          },
        },
      ] as Interview[];

      const searchEngine = getSearchEngine(malformedInterviews);
      
      // Should not crash
      const results = searchEngine.search('Test');
      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    test('should handle interviews with null/undefined fields', () => {
      const interviewsWithNulls = [
        {
          id: '1',
          metadata: {
            interviewee: null,
            summary: undefined,
            date: null,
          },
        },
        {
          id: '2',
          metadata: {
            interviewee: 'Valid Person',
            summary: 'Valid summary',
            date: '2023-01-01',
          },
        },
      ] as any as Interview[];

      const searchEngine = getSearchEngine(interviewsWithNulls);
      
      // Should handle gracefully
      const results = searchEngine.search('Valid');
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].item.metadata.interviewee).toBe('Valid Person');
    });

    test('should handle extremely long search queries', () => {
      const normalInterviews: Interview[] = [
        {
          id: '1',
          metadata: {
            interviewee: 'Test Person',
            summary: 'Test summary',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];

      const searchEngine = getSearchEngine(normalInterviews);
      
      // Test with very long query
      const longQuery = 'a'.repeat(10000);
      const results = searchEngine.search(longQuery);
      
      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    test('should handle special characters in search queries', () => {
      const interviews: Interview[] = [
        {
          id: '1',
          metadata: {
            interviewee: 'Test Person with Special Characters: äöü ß',
            summary: 'Summary with symbols !@#$%^&*()',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];

      const searchEngine = getSearchEngine(interviews);
      
      const specialQueries = [
        '!@#$%^&*()',
        'äöü',
        'ß',
        '<script>alert("test")</script>',
        '\\n\\t\\r',
        '""',
        "''",
        '`',
      ];

      specialQueries.forEach(query => {
        const results = searchEngine.search(query);
        expect(results).toBeDefined();
        expect(Array.isArray(results)).toBe(true);
      });
    });
  });

  describe('Search Engine Robustness', () => {
    test('should handle concurrent searches without conflicts', async () => {
      const interviews: Interview[] = Array.from({ length: 100 }, (_, i) => ({
        id: `interview-${i}`,
        metadata: {
          interviewee: `Person ${i}`,
          summary: `Summary for interview ${i}`,
        },
        assets: { video: '', subtitles: {} },
        transcripts: [],
      }));

      const searchEngine = getSearchEngine(interviews);
      
      // Run multiple searches concurrently
      const queries = ['Person', 'Summary', 'interview', '1', '5'];
      const promises = queries.map(query => 
        Promise.resolve(searchEngine.search(query))
      );

      const results = await Promise.all(promises);
      
      expect(results.length).toBe(queries.length);
      results.forEach(result => {
        expect(Array.isArray(result)).toBe(true);
      });
    });

    test('should maintain performance with large datasets', () => {
      // Create large dataset
      const largeDataset: Interview[] = Array.from({ length: 1000 }, (_, i) => ({
        id: `interview-${i}`,
        metadata: {
          interviewee: `Person ${i} from City ${i % 10}`,
          summary: `This is a detailed summary for interview ${i} containing various keywords and information about the person's background and experiences.`,
        },
        assets: { video: '', subtitles: {} },
        transcripts: [],
      }));

      const searchEngine = getSearchEngine(largeDataset);
      
      const startTime = performance.now();
      const results = searchEngine.search('Person');
      const endTime = performance.now();
      
      const searchTime = endTime - startTime;
      
      expect(searchTime).toBeLessThan(1000); // Should complete in under 1 second
      expect(results.length).toBeGreaterThan(0);
    });

    test('should handle memory pressure gracefully', () => {
      // Create dataset with large text content
      const memoryIntensiveDataset: Interview[] = Array.from({ length: 100 }, (_, i) => ({
        id: `interview-${i}`,
        metadata: {
          interviewee: `Person ${i}`,
          summary: 'Large summary content '.repeat(1000), // Large text
        },
        assets: { video: '', subtitles: {} },
        transcripts: [],
      }));

      const searchEngine = getSearchEngine(memoryIntensiveDataset);
      
      // Should initialize without crashing
      expect(searchEngine).toBeDefined();
      
      // Should perform searches without memory issues
      const results = searchEngine.search('Person');
      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('Filter Edge Cases', () => {
    test('should handle filters with no matching data', () => {
      const interviews: Interview[] = [
        {
          id: '1',
          metadata: {
            interviewee: 'John Doe',
            summary: 'Test summary',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];

      const searchEngine = getSearchEngine(interviews);
      
      // Filter by non-existent interviewee
      const results = searchEngine.search('', {
        filters: { interviewee: 'Non-existent Person' },
      });
      
      expect(results).toEqual([]);
    });

    test('should handle invalid filter values', () => {
      const interviews: Interview[] = [
        {
          id: '1',
          metadata: {
            interviewee: 'John Doe',
            summary: 'Test summary',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];

      const searchEngine = getSearchEngine(interviews);
      
      // Test with invalid filter values
      const invalidFilters = [
        { interviewee: null },
        { interviewee: undefined },
        { interviewee: '' },
        { language: 'invalid-language' },
        { dateRange: { start: 'invalid-date', end: 'invalid-date' } },
      ];

      invalidFilters.forEach(filter => {
        const results = searchEngine.search('John', { filters: filter as any });
        expect(results).toBeDefined();
        expect(Array.isArray(results)).toBe(true);
      });
    });
  });

  describe('Search Options Edge Cases', () => {
    test('should handle invalid search options', () => {
      const interviews: Interview[] = [
        {
          id: '1',
          metadata: {
            interviewee: 'John Doe',
            summary: 'Test summary',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];

      const searchEngine = getSearchEngine(interviews);
      
      // Test with invalid options
      const invalidOptions = [
        { limit: -1 },
        { limit: 0 },
        { limit: Infinity },
        { limit: NaN },
        { includeSnippets: 'invalid' },
        { threshold: -1 },
        { threshold: 2 },
      ];

      invalidOptions.forEach(options => {
        const results = searchEngine.search('John', options as any);
        expect(results).toBeDefined();
        expect(Array.isArray(results)).toBe(true);
      });
    });

    test('should handle extremely large limit values', () => {
      const interviews: Interview[] = Array.from({ length: 10 }, (_, i) => ({
        id: `interview-${i}`,
        metadata: {
          interviewee: `Person ${i}`,
          summary: 'Test summary',
        },
        assets: { video: '', subtitles: {} },
        transcripts: [],
      }));

      const searchEngine = getSearchEngine(interviews);
      
      // Request more results than available
      const results = searchEngine.search('Person', { limit: 1000000 });
      
      expect(results.length).toBeLessThanOrEqual(interviews.length);
      expect(results.length).toBe(10); // Should return all available
    });
  });

  describe('Data Corruption Scenarios', () => {
    test('should handle corrupted interview IDs', () => {
      const corruptedInterviews = [
        {
          id: '', // Empty ID
          metadata: {
            interviewee: 'Person 1',
            summary: 'Summary 1',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
        {
          id: null, // Null ID
          metadata: {
            interviewee: 'Person 2',
            summary: 'Summary 2',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
        {
          // Missing ID entirely
          metadata: {
            interviewee: 'Person 3',
            summary: 'Summary 3',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ] as any as Interview[];

      const searchEngine = getSearchEngine(corruptedInterviews);
      
      // Should handle gracefully
      const results = searchEngine.search('Person');
      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    test('should handle mixed data types in metadata', () => {
      const mixedTypeInterviews = [
        {
          id: '1',
          metadata: {
            interviewee: 123, // Number instead of string
            summary: ['array', 'instead', 'of', 'string'], // Array instead of string
            date: { year: 2023, month: 1 }, // Object instead of string
          },
        },
        {
          id: '2',
          metadata: {
            interviewee: true, // Boolean instead of string
            summary: null,
            date: undefined,
          },
        },
      ] as any as Interview[];

      const searchEngine = getSearchEngine(mixedTypeInterviews);
      
      // Should not crash
      const results = searchEngine.search('test');
      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('Performance Edge Cases', () => {
    test('should handle rapid successive searches', async () => {
      const interviews: Interview[] = Array.from({ length: 50 }, (_, i) => ({
        id: `interview-${i}`,
        metadata: {
          interviewee: `Person ${i}`,
          summary: `Summary ${i}`,
        },
        assets: { video: '', subtitles: {} },
        transcripts: [],
      }));

      const searchEngine = getSearchEngine(interviews);
      
      // Perform many searches in rapid succession
      const rapidSearches = Array.from({ length: 100 }, (_, i) => 
        searchEngine.search(`Person ${i % 10}`)
      );

      // All searches should complete successfully
      rapidSearches.forEach(results => {
        expect(results).toBeDefined();
        expect(Array.isArray(results)).toBe(true);
      });
    });

    test('should handle search during data updates', () => {
      let interviews: Interview[] = [
        {
          id: '1',
          metadata: {
            interviewee: 'Original Person',
            summary: 'Original summary',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];

      let searchEngine = getSearchEngine(interviews);
      
      // Perform initial search
      let results = searchEngine.search('Original');
      expect(results.length).toBe(1);
      
      // Simulate data update by creating new search engine
      interviews = [
        ...interviews,
        {
          id: '2',
          metadata: {
            interviewee: 'New Person',
            summary: 'New summary',
          },
          assets: { video: '', subtitles: {} },
          transcripts: [],
        },
      ];
      
      searchEngine = getSearchEngine(interviews);
      
      // Search should work with updated data
      results = searchEngine.search('New');
      expect(results.length).toBe(1);
      expect(results[0].item.metadata.interviewee).toBe('New Person');
    });
  });
});

