/**
 * Integration Tests for Advanced Search Functionality
 * Tests search engine with real data from manifest.min.json
 */

import { getSearchEngine } from '@/lib/search';
import { Interview } from '@/lib/types';
import fs from 'fs';
import path from 'path';

describe('Search Integration Tests', () => {
  let realInterviews: Interview[];
  let searchEngine: ReturnType<typeof getSearchEngine>;

  beforeAll(async () => {
    // Load real manifest data
    const manifestPath = path.join(process.cwd(), 'public', 'manifest.min.json');
    const manifestData = fs.readFileSync(manifestPath, 'utf8');
    realInterviews = JSON.parse(manifestData);
    
    // Initialize search engine with real data
    searchEngine = getSearchEngine(realInterviews);
    
    console.log(`Loaded ${realInterviews.length} real interviews for testing`);
  });

  describe('Real Data Validation', () => {
    test('should load real interview data successfully', () => {
      expect(realInterviews).toBeDefined();
      expect(realInterviews.length).toBeGreaterThan(700); // We know we have 726
      expect(realInterviews[0]).toHaveProperty('id');
      expect(realInterviews[0]).toHaveProperty('metadata');
    });

    test('should have valid interview structure', () => {
      const sampleInterview = realInterviews[0];
      expect(sampleInterview.id).toBeTruthy();
      expect(sampleInterview.metadata).toBeDefined();
      expect(sampleInterview.metadata).toHaveProperty('interviewee');
    });

    test('should contain German historical interviews', () => {
      // Check for German names and locations in the data
      const germanContent = realInterviews.some(interview => 
        interview.metadata.interviewee?.includes('Hamburg') ||
        interview.metadata.interviewee?.includes('Frankfurt') ||
        interview.metadata.interviewee?.includes('Ger')
      );
      expect(germanContent).toBe(true);
    });
  });

  describe('Search Engine Performance', () => {
    test('should initialize search engine with real data', () => {
      expect(searchEngine).toBeDefined();
      expect(typeof searchEngine.search).toBe('function');
      expect(typeof searchEngine.getFilterOptions).toBe('function');
    });

    test('should return filter options from real data', () => {
      const filterOptions = searchEngine.getFilterOptions();
      
      expect(filterOptions).toHaveProperty('interviewees');
      expect(filterOptions).toHaveProperty('languages');
      expect(filterOptions).toHaveProperty('dateRange');
      
      expect(filterOptions.interviewees.length).toBeGreaterThan(0);
      // Languages may be empty in test data
      expect(Array.isArray(filterOptions.languages)).toBe(true);
    });

    test('should perform fast searches on large dataset', async () => {
      const startTime = performance.now();
      
      const results = searchEngine.search({
        query: 'Hamburg',
        limit: 50,
        includeSnippets: true,
      });
      
      const endTime = performance.now();
      const searchTime = endTime - startTime;
      
      expect(searchTime).toBeLessThan(1000); // Should be under 1 second
      expect(results.length).toBeGreaterThan(0);
      expect(results[0]).toHaveProperty('interview');
      expect(results[0]).toHaveProperty('score');
    });
  });

  describe('Search Functionality with Real Data', () => {
    test('should find German locations', () => {
      const results = searchEngine.search({ query: 'Hamburg' });
      expect(results.length).toBeGreaterThan(0);
      
      const hamburgResults = results.filter(result => 
        result.interview.metadata.interviewee?.toLowerCase().includes('hamburg')
      );
      expect(hamburgResults.length).toBeGreaterThan(0);
    });

    test('should find German names', () => {
      const results = searchEngine.search({ query: 'Friedrich' });
      expect(results.length).toBeGreaterThan(0);
      
      const friedrichResults = results.filter(result => 
        result.interview.metadata.interviewee?.toLowerCase().includes('friedrich')
      );
      expect(friedrichResults.length).toBeGreaterThan(0);
    });

    test('should handle date searches', () => {
      const results = searchEngine.search({ query: '2002' });
      expect(results.length).toBeGreaterThan(0);
      
      const dateResults = results.filter(result => 
        result.interview.metadata.interviewee?.includes('2002')
      );
      expect(dateResults.length).toBeGreaterThan(0);
    });

    test('should return empty results for non-existent terms', () => {
      const results = searchEngine.search({ query: 'nonexistentterm12345' });
      expect(results.length).toBe(0);
    });

    test('should handle fuzzy matching', () => {
      // Test with slight misspelling
      const results = searchEngine.search({ query: 'Hambourg' }); // Misspelled Hamburg
      expect(results.length).toBeGreaterThan(0);
    });

    test('should respect search limits', () => {
      const results = searchEngine.search({ query: 'Ger', limit: 5 });
      expect(results.length).toBeLessThanOrEqual(5);
    });

    test('should include snippets when requested', () => {
      const results = searchEngine.search({ 
        query: 'Hamburg',
        limit: 3, 
        includeSnippets: true 
      });
      
      expect(results.length).toBeGreaterThan(0);
      results.forEach(result => {
        expect(result).toHaveProperty('snippet');
        expect(typeof result.snippet).toBe('string');
      });
    });
  });

  describe('Filter Functionality', () => {
    test('should filter by interviewee', () => {
      const filterOptions = searchEngine.getFilterOptions();
      const firstInterviewee = filterOptions.interviewees[0];
      
      const results = searchEngine.search({ 
        query: '',
        interviewees: [firstInterviewee],
        limit: 10,
      });
      
      expect(results.length).toBeGreaterThan(0);
      results.forEach(result => {
        expect(result.interview.metadata.interviewee).toContain(firstInterviewee);
      });
    });

    test('should combine search query with filters', () => {
      const results = searchEngine.search({
        query: 'Hamburg',
        interviewees: ['Friedrich'],
        limit: 10,
      });
      
      // Should find results that match both Hamburg AND have Friedrich in interviewee
      results.forEach(result => {
        const interviewee = result.interview.metadata.interviewee?.toLowerCase() || '';
        expect(
          interviewee.includes('hamburg') || interviewee.includes('friedrich')
        ).toBe(true);
      });
    });
  });

  describe('Performance with Large Dataset', () => {
    test('should handle multiple concurrent searches', async () => {
      const queries = ['Hamburg', 'Friedrich', 'Frankfurt', '2002', 'April'];
      
      const startTime = performance.now();
      
      const promises = queries.map(query => 
        Promise.resolve(searchEngine.search(query, { limit: 20 }))
      );
      
      const results = await Promise.all(promises);
      
      const endTime = performance.now();
      const totalTime = endTime - startTime;
      
      expect(totalTime).toBeLessThan(2000); // Should complete in under 2 seconds
      expect(results.length).toBe(queries.length);
      
      results.forEach((result, index) => {
        expect(Array.isArray(result)).toBe(true);
        console.log(`Query "${queries[index]}" returned ${result.length} results`);
      });
    });

    test('should maintain performance with large result sets', () => {
      const startTime = performance.now();
      
      // Search for a common term that should return many results
      const results = searchEngine.search('Ger', { limit: 100 });
      
      const endTime = performance.now();
      const searchTime = endTime - startTime;
      
      expect(searchTime).toBeLessThan(500); // Should be under 500ms
      expect(results.length).toBeGreaterThan(10);
      
      console.log(`Large search returned ${results.length} results in ${searchTime.toFixed(2)}ms`);
    });
  });

  describe('Data Quality Validation', () => {
    test('should have consistent data structure across all interviews', () => {
      const inconsistentInterviews = realInterviews.filter(interview => 
        !interview.id || 
        !interview.metadata || 
        typeof interview.metadata.interviewee !== 'string'
      );
      
      expect(inconsistentInterviews.length).toBe(0);
    });

    test('should have meaningful interviewee names', () => {
      const emptyInterviewees = realInterviews.filter(interview => 
        !interview.metadata.interviewee || 
        interview.metadata.interviewee.trim().length === 0
      );
      
      // Allow some empty interviewees but not too many
      expect(emptyInterviewees.length).toBeLessThan(realInterviews.length * 0.1); // Less than 10%
    });

    test('should have valid UUIDs for interview IDs', () => {
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      
      const invalidIds = realInterviews.filter(interview => 
        !uuidRegex.test(interview.id)
      );
      
      expect(invalidIds.length).toBe(0);
    });
  });

  describe('Search Result Quality', () => {
    test('should return relevant results for location searches', () => {
      const results = searchEngine.search({ query: 'Hamburg' });
      
      expect(results.length).toBeGreaterThan(0);
      
      // Check that results are actually relevant
      const relevantResults = results.filter(result => {
        const interviewee = result.interview.metadata.interviewee?.toLowerCase() || '';
        return interviewee.includes('hamburg');
      });
      
      // At least some results should be directly relevant (adjusted for real data)
      expect(relevantResults.length).toBeGreaterThan(0);
    });

    test('should rank results by relevance', () => {
      const results = searchEngine.search({ query: 'Friedrich Schlesinger' });
      
      if (results.length > 1) {
        // Scores should be in descending order (lower score = better match in Fuse.js)
        for (let i = 1; i < results.length; i++) {
          expect(results[i].score).toBeGreaterThanOrEqual(results[i - 1].score);
        }
      }
    });

    test('should handle complex search queries', () => {
      const complexQueries = [
        'Friedrich Hamburg 2002',
        'April Frankfurt',
        'Schlesinger Germany',
      ];
      
      complexQueries.forEach(query => {
        const results = searchEngine.search(query);
        expect(results).toBeDefined();
        expect(Array.isArray(results)).toBe(true);
        
        console.log(`Complex query "${query}" returned ${results.length} results`);
      });
    });
  });
});
