# Integration Testing Report

## Summary

- **Test Run Date**: 2025-07-20T14:46:12.929Z
- **Total Test Suites**: 4
- **Passed**: 0
- **Failed**: 4
- **Total Duration**: 10.18 seconds

## Test Suite Results


### Unit Tests

- **Status**: ❌ FAILED
- **Duration**: 3.87 seconds
- **Description**: Basic unit tests for components and utilities
- **Command**: `npm run test -- --passWithNoTests`

**Error Output:**
```
Command failed: npm run test -- --passWithNoTests
● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

FAIL tests/integration/search-integration.test.ts
  ● Console

    console.log
      Loaded 726 real interviews for testing

      at Object.log (tests/integration/search-integration.test.ts:24:13)

    console.log
      Query "Hamburg" returned 50 results

      at log (tests/integration/search-integration.test.ts:202:17)
          at Array.forEach (<anonymous>)

    console.log
      Query "Friedrich" returned 50 results

      at log (tests/integration/search-integration.test.ts:202:17)
          at Array.forEach (<anonymous>)

    console.log
      Query "Frankfurt" returned 50 results

      at log (tests/integration/search-integration.test.ts:202:17)
          at Array.forEach (<anonymous>)

    console.log
      Query "2002" returned 50 results

      at log (tests/integration/search-integration.test.ts:202:17)
          at Array.forEach (<anonymous>)

    console.log
      Query "April" returned 50 results

      at log (tests/integration/search-integration.test.ts:202:17)
          at Array.forEach (<anonymous>)

    console.log
      Large search returned 50 results in 0.03ms

      at Object.log (tests/integration/search-integration.test.ts:218:15)

    console.log
      Complex query "Friedrich Hamburg 2002" returned 50 results

      at log (tests/integration/search-integration.test.ts:293:17)
          at Array.forEach (<anonymous>)

    console.log
      Complex query "April Frankfurt" returned 50 results

      at log (tests/integration/search-integration.test.ts:293:17)
          at Array.forEach (<anonymous>)

    console.log
      Complex query "Schlesinger Germany" returned 50 results

      at log (tests/integration/search-integration.test.ts:293:17)
          at Array.forEach (<anonymous>)

  ● Search Integration Tests › Search Engine Performance › should return filter options from real data

    expect(received).toBeGreaterThan(expected)

    Expected: > 0
    Received:   0

      66 |       
      67 |       expect(filterOptions.interviewees.length).toBeGreaterThan(0);
    > 68 |       expect(filterOptions.languages.length).toBeGreaterThan(0);
         |                                              ^
      69 |     });
      70 |
      71 |     test('should perform fast searches on large dataset', async () => {

      at Object.toBeGreaterThan (tests/integration/search-integration.test.ts:68:46)

  ● Search Integration Tests › Search Engine Performance › should perform fast searches on large dataset

    expect(received).toHaveProperty(path)

    Expected path: "item"
    Received path: []

    Received value: {"context": "No summary available", "interview": {"id": "225f0880-e414-43cd-b3a5-2bd6e5642f07", "metadata": {"date": null, "interviewee": "01", "summary": ""}}, "matchedField": "summary", "score": 0, "snippet": "No summary available"}

      82 |       expect(searchTime).toBeLessThan(1000); // Should be under 1 second
      83 |       expect(results.length).toBeGreaterThan(0);
    > 84 |       expect(results[0]).toHaveProperty('item');
         |                          ^
      85 |       expect(results[0]).toHaveProperty('score');
      86 |     });
      87 |   });

      at Object.toHaveProperty (tests/integration/search-integration.test.ts:84:26)

  ● Search Integration Tests › Search Functionality with Real Data › should find German locations

    TypeError: Cannot read properties of undefined (reading 'metadata')

      93 |       
      94 |       const hamburgResults = results.filter(result => 
    > 95 |         result.item.metadata.interviewee?.toLowerCase().includes('hamburg')
         |                     ^
      96 |       );
      97 |       expect(hamburgResults.length).toBeGreaterThan(0);
      98 |     });

      at metadata (tests/integration/search-integration.test.ts:95:21)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:94:38)

  ● Search Integration Tests › Search Functionality with Real Data › should find German names

    TypeError: Cannot read properties of undefined (reading 'metadata')

      103 |       
      104 |       const friedrichResults = results.filter(result => 
    > 105 |         result.item.metadata.interviewee?.toLowerCase().includes('friedrich')
          |                     ^
      106 |       );
      107 |       expect(friedrichResults.length).toBeGreaterThan(0);
      108 |     });

      at metadata (tests/integration/search-integration.test.ts:105:21)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:104:40)

  ● Search Integration Tests › Search Functionality with Real Data › should handle date searches

    TypeError: Cannot read properties of undefined (reading 'metadata')

      113 |       
      114 |       const dateResults = results.filter(result => 
    > 115 |         result.item.metadata.interviewee?.includes('2002')
          |                     ^
      116 |       );
      117 |       expect(dateResults.length).toBeGreaterThan(0);
      118 |     });

      at metadata (tests/integration/search-integration.test.ts:115:21)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:114:35)

  ● Search Integration Tests › Search Functionality with Real Data › should return empty results for non-existent terms

    expect(received).toBe(expected) // Object.is equality

    Expected: 0
    Received: 50

      120 |     test('should return empty results for non-existent terms', () => {
      121 |       const results = searchEngine.search('nonexistentterm12345');
    > 122 |       expect(results.length).toBe(0);
          |                              ^
      123 |     });
      124 |
      125 |     test('should handle fuzzy matching', () => {

      at Object.toBe (tests/integration/search-integration.test.ts:122:30)

  ● Search Integration Tests › Search Functionality with Real Data › should respect search limits

    expect(received).toBeLessThanOrEqual(expected)

    Expected: <= 5
    Received:    50

      131 |     test('should respect search limits', () => {
      132 |       const results = searchEngine.search('Ger', { limit: 5 });
    > 133 |       expect(results.length).toBeLessThanOrEqual(5);
          |                              ^
      134 |     });
      135 |
      136 |     test('should include snippets when requested', () => {

      at Object.toBeLessThanOrEqual (tests/integration/search-integration.test.ts:133:30)

  ● Search Integration Tests › Filter Functionality › should filter by interviewee

    TypeError: Cannot read properties of undefined (reading 'metadata')

      160 |       expect(results.length).toBeGreaterThan(0);
      161 |       results.forEach(result => {
    > 162 |         expect(result.item.metadata.interviewee).toBe(firstInterviewee);
          |                            ^
      163 |       });
      164 |     });
      165 |

      at metadata (tests/integration/search-integration.test.ts:162:28)
          at Array.forEach (<anonymous>)
      at Object.forEach (tests/integration/search-integration.test.ts:161:15)

  ● Search Integration Tests › Filter Functionality › should combine search query with filters

    TypeError: Cannot read properties of undefined (reading 'metadata')

      172 |       // Should find results that match both Hamburg AND have Friedrich in interviewee
      173 |       results.forEach(result => {
    > 174 |         const interviewee = result.item.metadata.interviewee?.toLowerCase() || '';
          |                                         ^
      175 |         expect(
      176 |           interviewee.includes('hamburg') || interviewee.includes('friedrich')
      177 |         ).toBe(true);

      at metadata (tests/integration/search-integration.test.ts:174:41)
          at Array.forEach (<anonymous>)
      at Object.forEach (tests/integration/search-integration.test.ts:173:15)

  ● Search Integration Tests › Search Result Quality › should return relevant results for location searches

    TypeError: Cannot read properties of undefined (reading 'metadata')

      260 |       // Check that results are actually relevant
      261 |       const relevantResults = results.filter(result => {
    > 262 |         const interviewee = result.item.metadata.interviewee?.toLowerCase() || '';
          |                                         ^
      263 |         return interviewee.includes('hamburg');
      264 |       });
      265 |       

      at metadata (tests/integration/search-integration.test.ts:262:41)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:261:39)

FAIL tests/edge-cases/error-handling.test.ts
  ● Edge Case and Error Handling Tests › Malformed Data Handling › should handle interviews with missing metadata

    TypeError: Cannot read properties of null (reading 'summary')

      84 |       interview,
      85 |       score: 0,
    > 86 |       snippet: this.generateSnippet(interview.metadata.summary || 'No summary available', ''),
         |                                                        ^
      87 |       context: interview.metadata.summary || 'No summary available',
      88 |       matchedField: 'summary',
      89 |     }));

      at summary (lib/search.ts:86:56)
          at Array.map (<anonymous>)
      at SearchEngine.map [as getAllInterviews] (lib/search.ts:83:35)
      at SearchEngine.getAllInterviews [as search] (lib/search.ts:63:19)
      at Object.search (tests/edge-cases/error-handling.test.ts:49:36)

  ● Edge Case and Error Handling Tests › Malformed Data Handling › should handle interviews with null/undefined fields

    TypeError: Cannot read properties of undefined (reading 'metadata')

      77 |       const results = searchEngine.search('Valid');
      78 |       expect(results.length).toBeGreaterThan(0);
    > 79 |       expect(results[0].item.metadata.interviewee).toBe('Valid Person');
         |                              ^
      80 |     });
      81 |
      82 |     test('should handle extremely long search queries', () => {

      at Object.metadata (tests/edge-cases/error-handling.test.ts:79:30)

  ● Edge Case and Error Handling Tests › Filter Edge Cases › should handle filters with no matching data

    expect(received).toEqual(expected) // deep equality

    - Expected  -  1
    + Received  + 20

    - Array []
    + Array [
    +   Object {
    +     "context": "Test summary",
    +     "interview": Object {
    +       "assets": Object {
    +         "subtitles": Object {},
    +         "video": "",
    +       },
    +       "id": "1",
    +       "metadata": Object {
    +         "interviewee": "John Doe",
    +         "summary": "Test summary",
    +       },
    +       "transcripts": Array [],
    +     },
    +     "matchedField": "summary",
    +     "score": 0,
    +     "snippet": "Test summary",
    +   },
    + ]

      234 |       });
      235 |       
    > 236 |       expect(results).toEqual([]);
          |                       ^
      237 |     });
      238 |
      239 |     test('should handle invalid filter values', () => {

      at Object.toEqual (tests/edge-cases/error-handling.test.ts:236:23)

  ● Edge Case and Error Handling Tests › Performance Edge Cases › should handle search during data updates

    expect(received).toBe(expected) // Object.is equality

    Expected: 1
    Received: 2

      456 |       // Search should work with updated data
      457 |       results = searchEngine.search('New');
    > 458 |       expect(results.length).toBe(1);
          |                              ^
      459 |       expect(results[0].item.metadata.interviewee).toBe('New Person');
      460 |     });
      461 |   });

      at Object.toBe (tests/edge-cases/error-handling.test.ts:458:30)

FAIL tests/security/admin-auth.test.ts
  ● Test suite failed to run

    ReferenceError: Request is not defined

       6 | import { NextRequest } from 'next/server';
       7 | import { withAdminAuth, getAuthenticatedUser } from '@/lib/auth';
    >  8 |
         | ^
       9 | // Mock Next.js request for testing
      10 | function createMockRequest(options: {
      11 |   headers?: Record<string, string>;

      at Object.Request (node_modules/.pnpm/next@15.2.4_@babel+core@7.28.0_@playwright+test@1.54.1_react-dom@19.1.0_react@19.1.0__react@19.1.0/node_modules/next/src/server/web/spec-extension/request.ts:14:34)
      at Object.<anonymous> (node_modules/.pnpm/next@15.2.4_@babel+core@7.28.0_@playwright+test@1.54.1_react-dom@19.1.0_react@19.1.0__react@19.1.0/node_modules/next/server.js:2:16)
      at Object.<anonymous> (tests/security/admin-auth.test.ts:8:17)

FAIL tests/e2e/search-workflow.spec.ts
  ● Test suite failed to run

    Playwright Test needs to be invoked via 'npx playwright test' and excluded from Jest test runs.
    Creating one directory for Playwright tests and one for Jest is the recommended way of doing it.
    See https://playwright.dev/docs/intro for more information about Playwright Test.

       6 | import { test, expect } from '@playwright/test';
       7 |
    >  8 | test.describe('Search Workflow E2E Tests', () => {
         |      ^
       9 |   test.beforeEach(async ({ page }) => {
      10 |     // Navigate to the application
      11 |     await page.goto('/');

      at throwIfRunningInsideJest (node_modules/.pnpm/playwright@1.54.1/node_modules/playwright/lib/common/testType.js:272:11)
      at TestTypeImpl._describe (node_modules/.pnpm/playwright@1.54.1/node_modules/playwright/lib/common/testType.js:113:5)
      at Function.describe (node_modules/.pnpm/playwright@1.54.1/node_modules/playwright/lib/transform/transform.js:275:12)
      at Object.describe (tests/e2e/search-workflow.spec.ts:8:6)

Test Suites: 4 failed, 4 total
Tests:       14 failed, 25 passed, 39 total
Snapshots:   0 total
Time:        2.629 s
Ran all test suites.

```


\n
### Integration Tests

- **Status**: ❌ FAILED
- **Duration**: 2.15 seconds
- **Description**: Search functionality with real data validation
- **Command**: `npm run test:integration`

**Error Output:**
```
Command failed: npm run test:integration
● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

FAIL tests/integration/search-integration.test.ts
  Search Integration Tests
    Real Data Validation
      ✓ should load real interview data successfully (3 ms)
      ✓ should have valid interview structure (1 ms)
      ✓ should contain German historical interviews (1 ms)
    Search Engine Performance
      ✓ should initialize search engine with real data
      ✕ should return filter options from real data (2 ms)
      ✕ should perform fast searches on large dataset (1 ms)
    Search Functionality with Real Data
      ✕ should find German locations
      ✕ should find German names
      ✕ should handle date searches
      ✕ should return empty results for non-existent terms (1 ms)
      ✓ should handle fuzzy matching
      ✕ should respect search limits
      ✓ should include snippets when requested (18 ms)
    Filter Functionality
      ✕ should filter by interviewee (1 ms)
      ✕ should combine search query with filters
    Performance with Large Dataset
      ✓ should handle multiple concurrent searches (4 ms)
      ✓ should maintain performance with large result sets (1 ms)
    Data Quality Validation
      ✓ should have consistent data structure across all interviews (1 ms)
      ✓ should have meaningful interviewee names
      ✓ should have valid UUIDs for interview IDs (1 ms)
    Search Result Quality
      ✕ should return relevant results for location searches
      ✓ should rank results by relevance (2 ms)
      ✓ should handle complex search queries (3 ms)

  ● Search Integration Tests › Search Engine Performance › should return filter options from real data

    expect(received).toBeGreaterThan(expected)

    Expected: > 0
    Received:   0

      66 |       
      67 |       expect(filterOptions.interviewees.length).toBeGreaterThan(0);
    > 68 |       expect(filterOptions.languages.length).toBeGreaterThan(0);
         |                                              ^
      69 |     });
      70 |
      71 |     test('should perform fast searches on large dataset', async () => {

      at Object.toBeGreaterThan (tests/integration/search-integration.test.ts:68:46)

  ● Search Integration Tests › Search Engine Performance › should perform fast searches on large dataset

    expect(received).toHaveProperty(path)

    Expected path: "item"
    Received path: []

    Received value: {"context": "No summary available", "interview": {"id": "225f0880-e414-43cd-b3a5-2bd6e5642f07", "metadata": {"date": null, "interviewee": "01", "summary": ""}}, "matchedField": "summary", "score": 0, "snippet": "No summary available"}

      82 |       expect(searchTime).toBeLessThan(1000); // Should be under 1 second
      83 |       expect(results.length).toBeGreaterThan(0);
    > 84 |       expect(results[0]).toHaveProperty('item');
         |                          ^
      85 |       expect(results[0]).toHaveProperty('score');
      86 |     });
      87 |   });

      at Object.toHaveProperty (tests/integration/search-integration.test.ts:84:26)

  ● Search Integration Tests › Search Functionality with Real Data › should find German locations

    TypeError: Cannot read properties of undefined (reading 'metadata')

      93 |       
      94 |       const hamburgResults = results.filter(result => 
    > 95 |         result.item.metadata.interviewee?.toLowerCase().includes('hamburg')
         |                     ^
      96 |       );
      97 |       expect(hamburgResults.length).toBeGreaterThan(0);
      98 |     });

      at metadata (tests/integration/search-integration.test.ts:95:21)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:94:38)

  ● Search Integration Tests › Search Functionality with Real Data › should find German names

    TypeError: Cannot read properties of undefined (reading 'metadata')

      103 |       
      104 |       const friedrichResults = results.filter(result => 
    > 105 |         result.item.metadata.interviewee?.toLowerCase().includes('friedrich')
          |                     ^
      106 |       );
      107 |       expect(friedrichResults.length).toBeGreaterThan(0);
      108 |     });

      at metadata (tests/integration/search-integration.test.ts:105:21)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:104:40)

  ● Search Integration Tests › Search Functionality with Real Data › should handle date searches

    TypeError: Cannot read properties of undefined (reading 'metadata')

      113 |       
      114 |       const dateResults = results.filter(result => 
    > 115 |         result.item.metadata.interviewee?.includes('2002')
          |                     ^
      116 |       );
      117 |       expect(dateResults.length).toBeGreaterThan(0);
      118 |     });

      at metadata (tests/integration/search-integration.test.ts:115:21)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:114:35)

  ● Search Integration Tests › Search Functionality with Real Data › should return empty results for non-existent terms

    expect(received).toBe(expected) // Object.is equality

    Expected: 0
    Received: 50

      120 |     test('should return empty results for non-existent terms', () => {
      121 |       const results = searchEngine.search('nonexistentterm12345');
    > 122 |       expect(results.length).toBe(0);
          |                              ^
      123 |     });
      124 |
      125 |     test('should handle fuzzy matching', () => {

      at Object.toBe (tests/integration/search-integration.test.ts:122:30)

  ● Search Integration Tests › Search Functionality with Real Data › should respect search limits

    expect(received).toBeLessThanOrEqual(expected)

    Expected: <= 5
    Received:    50

      131 |     test('should respect search limits', () => {
      132 |       const results = searchEngine.search('Ger', { limit: 5 });
    > 133 |       expect(results.length).toBeLessThanOrEqual(5);
          |                              ^
      134 |     });
      135 |
      136 |     test('should include snippets when requested', () => {

      at Object.toBeLessThanOrEqual (tests/integration/search-integration.test.ts:133:30)

  ● Search Integration Tests › Filter Functionality › should filter by interviewee

    TypeError: Cannot read properties of undefined (reading 'metadata')

      160 |       expect(results.length).toBeGreaterThan(0);
      161 |       results.forEach(result => {
    > 162 |         expect(result.item.metadata.interviewee).toBe(firstInterviewee);
          |                            ^
      163 |       });
      164 |     });
      165 |

      at metadata (tests/integration/search-integration.test.ts:162:28)
          at Array.forEach (<anonymous>)
      at Object.forEach (tests/integration/search-integration.test.ts:161:15)

  ● Search Integration Tests › Filter Functionality › should combine search query with filters

    TypeError: Cannot read properties of undefined (reading 'metadata')

      172 |       // Should find results that match both Hamburg AND have Friedrich in interviewee
      173 |       results.forEach(result => {
    > 174 |         const interviewee = result.item.metadata.interviewee?.toLowerCase() || '';
          |                                         ^
      175 |         expect(
      176 |           interviewee.includes('hamburg') || interviewee.includes('friedrich')
      177 |         ).toBe(true);

      at metadata (tests/integration/search-integration.test.ts:174:41)
          at Array.forEach (<anonymous>)
      at Object.forEach (tests/integration/search-integration.test.ts:173:15)

  ● Search Integration Tests › Search Result Quality › should return relevant results for location searches

    TypeError: Cannot read properties of undefined (reading 'metadata')

      260 |       // Check that results are actually relevant
      261 |       const relevantResults = results.filter(result => {
    > 262 |         const interviewee = result.item.metadata.interviewee?.toLowerCase() || '';
          |                                         ^
      263 |         return interviewee.includes('hamburg');
      264 |       });
      265 |       

      at metadata (tests/integration/search-integration.test.ts:262:41)
          at Array.filter (<anonymous>)
      at Object.filter (tests/integration/search-integration.test.ts:261:39)

Test Suites: 1 failed, 1 total
Tests:       10 failed, 13 passed, 23 total
Snapshots:   0 total
Time:        0.857 s, estimated 1 s
Ran all test suites matching /tests\/integration/i.

```


\n
### Security Tests

- **Status**: ❌ FAILED
- **Duration**: 2.07 seconds
- **Description**: Admin authentication and security measures
- **Command**: `npm run test:security`

**Error Output:**
```
Command failed: npm run test:security
● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

FAIL tests/security/admin-auth.test.ts
  ● Test suite failed to run

    ReferenceError: Request is not defined

       6 | import { NextRequest } from 'next/server';
       7 | import { withAdminAuth, getAuthenticatedUser } from '@/lib/auth';
    >  8 |
         | ^
       9 | // Mock Next.js request for testing
      10 | function createMockRequest(options: {
      11 |   headers?: Record<string, string>;

      at Object.Request (node_modules/.pnpm/next@15.2.4_@babel+core@7.28.0_@playwright+test@1.54.1_react-dom@19.1.0_react@19.1.0__react@19.1.0/node_modules/next/src/server/web/spec-extension/request.ts:14:34)
      at Object.<anonymous> (node_modules/.pnpm/next@15.2.4_@babel+core@7.28.0_@playwright+test@1.54.1_react-dom@19.1.0_react@19.1.0__react@19.1.0/node_modules/next/server.js:2:16)
      at Object.<anonymous> (tests/security/admin-auth.test.ts:8:17)

Test Suites: 1 failed, 1 total
Tests:       0 total
Snapshots:   0 total
Time:        0.794 s
Ran all test suites matching /tests\/security/i.

```


\n
### Edge Case Tests

- **Status**: ❌ FAILED
- **Duration**: 2.09 seconds
- **Description**: Error handling and malformed data scenarios
- **Command**: `npm run test -- --testPathPattern=edge-cases`

**Error Output:**
```
Command failed: npm run test -- --testPathPattern=edge-cases
● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

● Validation Warning:

  Unknown option "moduleNameMapping" with value {"^@/(.*)$": "<rootDir>/$1"} was found.
  This is probably a typing mistake. Fixing it will remove this message.

  Configuration Documentation:
  https://jestjs.io/docs/configuration

FAIL tests/edge-cases/error-handling.test.ts
  Edge Case and Error Handling Tests
    Malformed Data Handling
      ✓ should handle empty interview array (3 ms)
      ✕ should handle interviews with missing metadata (1 ms)
      ✕ should handle interviews with null/undefined fields (1 ms)
      ✓ should handle extremely long search queries (2 ms)
      ✓ should handle special characters in search queries (1 ms)
    Search Engine Robustness
      ✓ should handle concurrent searches without conflicts (2 ms)
      ✓ should maintain performance with large datasets (5 ms)
      ✓ should handle memory pressure gracefully (29 ms)
    Filter Edge Cases
      ✕ should handle filters with no matching data (4 ms)
      ✓ should handle invalid filter values (1 ms)
    Search Options Edge Cases
      ✓ should handle invalid search options (1 ms)
      ✓ should handle extremely large limit values (1 ms)
    Data Corruption Scenarios
      ✓ should handle corrupted interview IDs
      ✓ should handle mixed data types in metadata (1 ms)
    Performance Edge Cases
      ✓ should handle rapid successive searches (19 ms)
      ✕ should handle search during data updates (2 ms)

  ● Edge Case and Error Handling Tests › Malformed Data Handling › should handle interviews with missing metadata

    TypeError: Cannot read properties of null (reading 'summary')

      84 |       interview,
      85 |       score: 0,
    > 86 |       snippet: this.generateSnippet(interview.metadata.summary || 'No summary available', ''),
         |                                                        ^
      87 |       context: interview.metadata.summary || 'No summary available',
      88 |       matchedField: 'summary',
      89 |     }));

      at summary (lib/search.ts:86:56)
          at Array.map (<anonymous>)
      at SearchEngine.map [as getAllInterviews] (lib/search.ts:83:35)
      at SearchEngine.getAllInterviews [as search] (lib/search.ts:63:19)
      at Object.search (tests/edge-cases/error-handling.test.ts:49:36)

  ● Edge Case and Error Handling Tests › Malformed Data Handling › should handle interviews with null/undefined fields

    TypeError: Cannot read properties of undefined (reading 'metadata')

      77 |       const results = searchEngine.search('Valid');
      78 |       expect(results.length).toBeGreaterThan(0);
    > 79 |       expect(results[0].item.metadata.interviewee).toBe('Valid Person');
         |                              ^
      80 |     });
      81 |
      82 |     test('should handle extremely long search queries', () => {

      at Object.metadata (tests/edge-cases/error-handling.test.ts:79:30)

  ● Edge Case and Error Handling Tests › Filter Edge Cases › should handle filters with no matching data

    expect(received).toEqual(expected) // deep equality

    - Expected  -  1
    + Received  + 20

    - Array []
    + Array [
    +   Object {
    +     "context": "Test summary",
    +     "interview": Object {
    +       "assets": Object {
    +         "subtitles": Object {},
    +         "video": "",
    +       },
    +       "id": "1",
    +       "metadata": Object {
    +         "interviewee": "John Doe",
    +         "summary": "Test summary",
    +       },
    +       "transcripts": Array [],
    +     },
    +     "matchedField": "summary",
    +     "score": 0,
    +     "snippet": "Test summary",
    +   },
    + ]

      234 |       });
      235 |       
    > 236 |       expect(results).toEqual([]);
          |                       ^
      237 |     });
      238 |
      239 |     test('should handle invalid filter values', () => {

      at Object.toEqual (tests/edge-cases/error-handling.test.ts:236:23)

  ● Edge Case and Error Handling Tests › Performance Edge Cases › should handle search during data updates

    expect(received).toBe(expected) // Object.is equality

    Expected: 1
    Received: 2

      456 |       // Search should work with updated data
      457 |       results = searchEngine.search('New');
    > 458 |       expect(results.length).toBe(1);
          |                              ^
      459 |       expect(results[0].item.metadata.interviewee).toBe('New Person');
      460 |     });
      461 |   });

      at Object.toBe (tests/edge-cases/error-handling.test.ts:458:30)

Test Suites: 1 failed, 1 total
Tests:       4 failed, 12 passed, 16 total
Snapshots:   0 total
Time:        0.854 s, estimated 1 s
Ran all test suites matching /edge-cases/i.

```




## Performance Testing


**Status**: ✅ Completed
**Details**: See performance test output above


## Recommendations

- Fix failing unit tests - check test output for specific failures\n- Resolve integration test failures - ensure search engine works with real data\n- Fix security issues - ensure admin authentication is properly implemented\n- Improve error handling - ensure system gracefully handles malformed data\n- Fix end-to-end test failures - ensure user workflows work correctly

---

*Report generated on 7/20/2025, 2:46:23 PM*
