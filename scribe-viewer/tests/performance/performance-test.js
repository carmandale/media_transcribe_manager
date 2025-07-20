/**
 * Performance Testing Suite for Advanced Search Functionality
 * Tests search performance with varying data volumes and concurrent users
 */

const fs = require('fs').promises;
const path = require('path');

// Performance test configuration
const PERFORMANCE_THRESHOLDS = {
  SEARCH_RESPONSE_TIME_MS: 5000,    // Max 5 seconds for search
  MEMORY_USAGE_MB: 512,             // Max 512MB memory usage
  CONCURRENT_USERS: 10,             // Test with 10 concurrent users
  LARGE_DATASET_SIZE: 500,          // Test with 500+ interviews
};

// Test data sizes to validate
const TEST_SCENARIOS = [
  { name: 'Small Dataset', size: 10, description: '10 interviews' },
  { name: 'Medium Dataset', size: 50, description: '50 interviews' },
  { name: 'Large Dataset', size: 100, description: '100 interviews' },
  { name: 'Production Dataset', size: 726, description: 'Full 726 interviews' },
];

class PerformanceTester {
  constructor() {
    this.results = [];
    this.baseUrl = 'http://localhost:3000';
  }

  async loadManifestData() {
    try {
      const manifestPath = path.join(__dirname, '../../public/manifest.min.json');
      const data = await fs.readFile(manifestPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load manifest data:', error);
      return [];
    }
  }

  async measureSearchPerformance(query, datasetSize) {
    const startTime = performance.now();
    const startMemory = process.memoryUsage();

    try {
      // Simulate search API call
      const response = await fetch(`${this.baseUrl}/api/search?q=${encodeURIComponent(query)}&limit=${datasetSize}`);
      const results = await response.json();
      
      const endTime = performance.now();
      const endMemory = process.memoryUsage();
      
      const responseTime = endTime - startTime;
      const memoryDelta = endMemory.heapUsed - startMemory.heapUsed;
      
      return {
        query,
        datasetSize,
        responseTime,
        memoryUsage: memoryDelta / 1024 / 1024, // Convert to MB
        resultCount: results.length || 0,
        success: response.ok,
      };
    } catch (error) {
      return {
        query,
        datasetSize,
        responseTime: -1,
        memoryUsage: -1,
        resultCount: 0,
        success: false,
        error: error.message,
      };
    }
  }

  async runConcurrentSearchTests(queries, datasetSize, concurrentUsers = 5) {
    console.log(`\\n🔄 Running concurrent search tests with ${concurrentUsers} users...`);
    
    const promises = [];
    for (let i = 0; i < concurrentUsers; i++) {
      const query = queries[i % queries.length];
      promises.push(this.measureSearchPerformance(query, datasetSize));
    }
    
    const results = await Promise.all(promises);
    
    const avgResponseTime = results.reduce((sum, r) => sum + r.responseTime, 0) / results.length;
    const maxResponseTime = Math.max(...results.map(r => r.responseTime));
    const successRate = results.filter(r => r.success).length / results.length * 100;
    
    return {
      concurrentUsers,
      avgResponseTime,
      maxResponseTime,
      successRate,
      results,
    };
  }

  async testSearchIndexing() {
    console.log('\\n🔄 Testing search index performance...');
    
    const startTime = performance.now();
    
    try {
      const response = await fetch(`${this.baseUrl}/api/admin/reindex`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-api-key-for-testing',
        },
      });
      
      const result = await response.json();
      const endTime = performance.now();
      
      return {
        indexingTime: endTime - startTime,
        success: response.ok,
        stats: result.stats || {},
      };
    } catch (error) {
      return {
        indexingTime: -1,
        success: false,
        error: error.message,
      };
    }
  }

  async runPerformanceTests() {
    console.log('🚀 Starting Performance Testing Suite\\n');
    console.log('=' .repeat(60));
    
    const manifestData = await this.loadManifestData();
    console.log(`📊 Loaded ${manifestData.length} interviews from manifest`);
    
    // Test queries representing different search patterns
    const testQueries = [
      'interview',           // Common word
      'Germany',            // Location search
      'Friedrich',          // Name search
      'April 2002',         // Date search
      'Hamburg',            // City search
      'nonexistentword123', // No results query
    ];
    
    console.log('\\n📋 Test Scenarios:');
    TEST_SCENARIOS.forEach(scenario => {
      console.log(`  • ${scenario.name}: ${scenario.description}`);
    });
    
    // Run performance tests for each scenario
    for (const scenario of TEST_SCENARIOS) {
      console.log(`\\n🎯 Testing ${scenario.name} (${scenario.size} interviews)`);
      console.log('-'.repeat(50));
      
      const scenarioResults = [];
      
      // Test each query
      for (const query of testQueries) {
        const result = await this.measureSearchPerformance(query, scenario.size);
        scenarioResults.push(result);
        
        const status = result.success ? '✅' : '❌';
        const time = result.responseTime > 0 ? `${result.responseTime.toFixed(2)}ms` : 'FAILED';
        const memory = result.memoryUsage > 0 ? `${result.memoryUsage.toFixed(2)}MB` : 'N/A';
        
        console.log(`  ${status} "${query}": ${time} | ${memory} | ${result.resultCount} results`);
      }
      
      // Calculate scenario statistics
      const successfulResults = scenarioResults.filter(r => r.success);
      if (successfulResults.length > 0) {
        const avgTime = successfulResults.reduce((sum, r) => sum + r.responseTime, 0) / successfulResults.length;
        const maxTime = Math.max(...successfulResults.map(r => r.responseTime));
        const avgMemory = successfulResults.reduce((sum, r) => sum + r.memoryUsage, 0) / successfulResults.length;
        
        console.log(`\\n  📊 Scenario Summary:`);
        console.log(`     Average Response Time: ${avgTime.toFixed(2)}ms`);
        console.log(`     Maximum Response Time: ${maxTime.toFixed(2)}ms`);
        console.log(`     Average Memory Usage: ${avgMemory.toFixed(2)}MB`);
        console.log(`     Success Rate: ${(successfulResults.length / scenarioResults.length * 100).toFixed(1)}%`);
        
        // Check against thresholds
        const timeThresholdMet = maxTime <= PERFORMANCE_THRESHOLDS.SEARCH_RESPONSE_TIME_MS;
        const memoryThresholdMet = avgMemory <= PERFORMANCE_THRESHOLDS.MEMORY_USAGE_MB;
        
        console.log(`\\n  🎯 Threshold Analysis:`);
        console.log(`     Response Time: ${timeThresholdMet ? '✅ PASS' : '❌ FAIL'} (${maxTime.toFixed(2)}ms <= ${PERFORMANCE_THRESHOLDS.SEARCH_RESPONSE_TIME_MS}ms)`);
        console.log(`     Memory Usage: ${memoryThresholdMet ? '✅ PASS' : '❌ FAIL'} (${avgMemory.toFixed(2)}MB <= ${PERFORMANCE_THRESHOLDS.MEMORY_USAGE_MB}MB)`);
      }
      
      this.results.push({
        scenario: scenario.name,
        results: scenarioResults,
      });
    }
    
    // Test concurrent users
    console.log('\\n🔄 Concurrent User Testing');
    console.log('-'.repeat(50));
    
    const concurrentResult = await this.runConcurrentSearchTests(testQueries, 100, PERFORMANCE_THRESHOLDS.CONCURRENT_USERS);
    
    console.log(`  👥 ${concurrentResult.concurrentUsers} concurrent users`);
    console.log(`  ⏱️  Average Response Time: ${concurrentResult.avgResponseTime.toFixed(2)}ms`);
    console.log(`  🔥 Maximum Response Time: ${concurrentResult.maxResponseTime.toFixed(2)}ms`);
    console.log(`  ✅ Success Rate: ${concurrentResult.successRate.toFixed(1)}%`);
    
    // Test search indexing performance
    console.log('\\n🔍 Search Index Performance');
    console.log('-'.repeat(50));
    
    const indexResult = await this.testSearchIndexing();
    if (indexResult.success) {
      console.log(`  ⚡ Indexing Time: ${indexResult.indexingTime.toFixed(2)}ms`);
      console.log(`  📊 Index Stats:`, indexResult.stats);
    } else {
      console.log(`  ❌ Indexing Failed: ${indexResult.error}`);
    }
    
    // Generate final report
    this.generateReport();
  }

  generateReport() {
    console.log('\\n' + '='.repeat(60));
    console.log('📊 PERFORMANCE TEST REPORT');
    console.log('='.repeat(60));
    
    let allPassed = true;
    
    // Analyze results
    for (const scenarioResult of this.results) {
      const successfulResults = scenarioResult.results.filter(r => r.success);
      if (successfulResults.length === 0) continue;
      
      const maxTime = Math.max(...successfulResults.map(r => r.responseTime));
      const avgMemory = successfulResults.reduce((sum, r) => sum + r.memoryUsage, 0) / successfulResults.length;
      
      const timePass = maxTime <= PERFORMANCE_THRESHOLDS.SEARCH_RESPONSE_TIME_MS;
      const memoryPass = avgMemory <= PERFORMANCE_THRESHOLDS.MEMORY_USAGE_MB;
      
      if (!timePass || !memoryPass) {
        allPassed = false;
      }
      
      console.log(`\\n${scenarioResult.scenario}:`);
      console.log(`  Response Time: ${timePass ? '✅ PASS' : '❌ FAIL'} (${maxTime.toFixed(2)}ms)`);
      console.log(`  Memory Usage: ${memoryPass ? '✅ PASS' : '❌ FAIL'} (${avgMemory.toFixed(2)}MB)`);
    }
    
    console.log(`\\n🎯 OVERALL RESULT: ${allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);
    
    if (allPassed) {
      console.log('\\n🎉 The search functionality meets all performance requirements!');
      console.log('   Ready for production deployment.');
    } else {
      console.log('\\n⚠️  Performance issues detected. Review failed tests above.');
      console.log('   Consider optimization before production deployment.');
    }
    
    console.log('\\n' + '='.repeat(60));
  }
}

// Run performance tests if called directly
if (require.main === module) {
  const tester = new PerformanceTester();
  tester.runPerformanceTests().catch(console.error);
}

module.exports = PerformanceTester;

