/**
 * Comprehensive Test Runner for Integration Testing Phase
 * Runs all test suites and generates production readiness report
 */

const { execSync } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

class IntegrationTestRunner {
  constructor() {
    this.results = {
      timestamp: new Date().toISOString(),
      summary: {
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
        duration: 0,
      },
      suites: [],
      performance: {},
      coverage: {},
      productionReadiness: {
        score: 0,
        criteria: [],
        recommendations: [],
      },
    };
  }

  async runTestSuite(name, command, description) {
    console.log(`\\n🔄 Running ${name}...`);
    console.log(`📝 ${description}`);
    console.log('-'.repeat(60));
    
    const startTime = Date.now();
    let success = false;
    let output = '';
    let error = '';
    
    try {
      output = execSync(command, { 
        cwd: process.cwd(),
        encoding: 'utf8',
        stdio: 'pipe',
        timeout: 300000, // 5 minutes timeout
      });
      success = true;
      console.log('✅ PASSED');
    } catch (err) {
      success = false;
      error = err.message;
      output = err.stdout || '';
      console.log('❌ FAILED');
      console.log(`Error: ${err.message}`);
    }
    
    const duration = Date.now() - startTime;
    
    const suite = {
      name,
      description,
      success,
      duration,
      output,
      error,
      command,
    };
    
    this.results.suites.push(suite);
    this.results.summary.duration += duration;
    
    if (success) {
      this.results.summary.passedTests++;
    } else {
      this.results.summary.failedTests++;
    }
    
    return suite;
  }

  async runPerformanceTests() {
    console.log('\\n🚀 Running Performance Tests...');
    
    try {
      // Check if dev server is running
      const serverCheck = execSync('curl -f http://localhost:3000 || echo "SERVER_DOWN"', { 
        encoding: 'utf8',
        stdio: 'pipe',
      });
      
      if (serverCheck.includes('SERVER_DOWN')) {
        console.log('⚠️  Development server not running. Starting server...');
        console.log('   Please run "npm run dev" in another terminal and restart tests.');
        
        this.results.performance = {
          error: 'Development server not running',
          recommendation: 'Start development server with "npm run dev" before running performance tests',
        };
        return;
      }
      
      // Run performance tests
      const PerformanceTester = require('./performance/performance-test.js');
      const tester = new PerformanceTester();
      
      console.log('Running comprehensive performance analysis...');
      await tester.runPerformanceTests();
      
      this.results.performance = {
        status: 'completed',
        details: 'See performance test output above',
      };
      
    } catch (error) {
      console.log('❌ Performance tests failed:', error.message);
      this.results.performance = {
        error: error.message,
        status: 'failed',
      };
    }
  }

  calculateProductionReadiness() {
    console.log('\\n📊 Calculating Production Readiness Score...');
    
    const criteria = [
      {
        name: 'Unit Tests Pass',
        weight: 20,
        passed: this.results.suites.find(s => s.name === 'Unit Tests')?.success || false,
        description: 'All unit tests pass successfully',
      },
      {
        name: 'Integration Tests Pass',
        weight: 25,
        passed: this.results.suites.find(s => s.name === 'Integration Tests')?.success || false,
        description: 'Search functionality works with real data',
      },
      {
        name: 'Security Tests Pass',
        weight: 20,
        passed: this.results.suites.find(s => s.name === 'Security Tests')?.success || false,
        description: 'Admin authentication and security measures work',
      },
      {
        name: 'Edge Case Handling',
        weight: 15,
        passed: this.results.suites.find(s => s.name === 'Edge Case Tests')?.success || false,
        description: 'System handles malformed data and error conditions',
      },
      {
        name: 'Performance Acceptable',
        weight: 10,
        passed: !this.results.performance.error,
        description: 'Performance tests complete without errors',
      },
      {
        name: 'E2E Tests Pass',
        weight: 10,
        passed: this.results.suites.find(s => s.name === 'E2E Tests')?.success || false,
        description: 'End-to-end user workflows work correctly',
      },
    ];
    
    let totalScore = 0;
    let maxScore = 0;
    
    criteria.forEach(criterion => {
      maxScore += criterion.weight;
      if (criterion.passed) {
        totalScore += criterion.weight;
      }
      
      const status = criterion.passed ? '✅' : '❌';
      console.log(`  ${status} ${criterion.name} (${criterion.weight}pts): ${criterion.description}`);
    });
    
    const score = Math.round((totalScore / maxScore) * 100);
    
    this.results.productionReadiness = {
      score,
      criteria,
      recommendations: this.generateRecommendations(criteria),
    };
    
    console.log(`\\n🎯 Production Readiness Score: ${score}/100`);
    
    if (score >= 90) {
      console.log('🎉 EXCELLENT - Ready for production deployment!');
    } else if (score >= 75) {
      console.log('✅ GOOD - Minor issues to address before production');
    } else if (score >= 60) {
      console.log('⚠️  FAIR - Several issues need attention');
    } else {
      console.log('❌ POOR - Significant work needed before production');
    }
    
    return score;
  }

  generateRecommendations(criteria) {
    const recommendations = [];
    
    criteria.forEach(criterion => {
      if (!criterion.passed) {
        switch (criterion.name) {
          case 'Unit Tests Pass':
            recommendations.push('Fix failing unit tests - check test output for specific failures');
            break;
          case 'Integration Tests Pass':
            recommendations.push('Resolve integration test failures - ensure search engine works with real data');
            break;
          case 'Security Tests Pass':
            recommendations.push('Fix security issues - ensure admin authentication is properly implemented');
            break;
          case 'Edge Case Handling':
            recommendations.push('Improve error handling - ensure system gracefully handles malformed data');
            break;
          case 'Performance Acceptable':
            recommendations.push('Address performance issues - start dev server and run performance tests');
            break;
          case 'E2E Tests Pass':
            recommendations.push('Fix end-to-end test failures - ensure user workflows work correctly');
            break;
        }
      }
    });
    
    if (recommendations.length === 0) {
      recommendations.push('All tests passing! Consider running additional stress tests before production deployment.');
    }
    
    return recommendations;
  }

  async generateReport() {
    const reportPath = path.join(process.cwd(), 'TESTING_REPORT.md');
    const productionReadinessPath = path.join(process.cwd(), 'PRODUCTION_READINESS.md');
    
    // Generate detailed testing report
    const testingReport = this.generateTestingReport();
    await fs.writeFile(reportPath, testingReport);
    
    // Generate production readiness report
    const productionReport = this.generateProductionReadinessReport();
    await fs.writeFile(productionReadinessPath, productionReport);
    
    console.log(`\\n📄 Reports generated:`);
    console.log(`   📋 Testing Report: ${reportPath}`);
    console.log(`   🚀 Production Readiness: ${productionReadinessPath}`);
  }

  generateTestingReport() {
    const { summary, suites, performance } = this.results;
    
    return `# Integration Testing Report

## Summary

- **Test Run Date**: ${this.results.timestamp}
- **Total Test Suites**: ${suites.length}
- **Passed**: ${summary.passedTests}
- **Failed**: ${summary.failedTests}
- **Total Duration**: ${(summary.duration / 1000).toFixed(2)} seconds

## Test Suite Results

${suites.map(suite => `
### ${suite.name}

- **Status**: ${suite.success ? '✅ PASSED' : '❌ FAILED'}
- **Duration**: ${(suite.duration / 1000).toFixed(2)} seconds
- **Description**: ${suite.description}
- **Command**: \`${suite.command}\`

${suite.error ? `**Error Output:**
\`\`\`
${suite.error}
\`\`\`` : ''}

${suite.output && suite.success ? `**Output Summary:**
\`\`\`
${suite.output.slice(0, 500)}${suite.output.length > 500 ? '...' : ''}
\`\`\`` : ''}
`).join('\\n')}

## Performance Testing

${performance.error ? `
**Status**: ❌ Failed
**Error**: ${performance.error}
**Recommendation**: ${performance.recommendation || 'Check performance test configuration'}
` : `
**Status**: ✅ Completed
**Details**: ${performance.details || 'Performance tests completed successfully'}
`}

## Recommendations

${this.results.productionReadiness.recommendations.map(rec => `- ${rec}`).join('\\n')}

---

*Report generated on ${new Date().toLocaleString()}*
`;
  }

  generateProductionReadinessReport() {
    const { score, criteria, recommendations } = this.results.productionReadiness;
    
    return `# Production Readiness Report

## Overall Score: ${score}/100

${score >= 90 ? '🎉 **EXCELLENT** - Ready for production deployment!' :
  score >= 75 ? '✅ **GOOD** - Minor issues to address before production' :
  score >= 60 ? '⚠️ **FAIR** - Several issues need attention' :
  '❌ **POOR** - Significant work needed before production'}

## Readiness Criteria

${criteria.map(criterion => `
### ${criterion.name} (${criterion.weight} points)

- **Status**: ${criterion.passed ? '✅ PASSED' : '❌ FAILED'}
- **Description**: ${criterion.description}
`).join('\\n')}

## Recommendations

${recommendations.map((rec, index) => `${index + 1}. ${rec}`).join('\\n')}

## Next Steps

${score >= 90 ? `
### Ready for Production! 🚀

Your application has passed all critical tests and is ready for production deployment. Consider:

1. **Final Performance Testing**: Run load tests with production-like data volumes
2. **Security Review**: Conduct final security audit of admin endpoints
3. **Deployment Planning**: Prepare deployment scripts and monitoring
4. **User Training**: Prepare documentation for end users
5. **Rollback Plan**: Ensure you have a rollback strategy ready

` : `
### Before Production Deployment

Address the following issues before deploying to production:

${recommendations.map((rec, index) => `${index + 1}. ${rec}`).join('\\n')}

After addressing these issues, re-run the test suite to verify fixes.
`}

## Test Coverage Summary

- **Search Functionality**: ${criteria.find(c => c.name === 'Integration Tests Pass')?.passed ? 'Validated with real data' : 'Needs attention'}
- **Security**: ${criteria.find(c => c.name === 'Security Tests Pass')?.passed ? 'Admin authentication working' : 'Security issues detected'}
- **Error Handling**: ${criteria.find(c => c.name === 'Edge Case Handling')?.passed ? 'Robust error handling' : 'Improve error handling'}
- **User Experience**: ${criteria.find(c => c.name === 'E2E Tests Pass')?.passed ? 'User workflows validated' : 'User experience issues'}
- **Performance**: ${criteria.find(c => c.name === 'Performance Acceptable')?.passed ? 'Performance acceptable' : 'Performance issues detected'}

---

*Report generated on ${new Date().toLocaleString()}*
*Integration Testing Phase - Advanced Search Functionality*
`;
  }

  async runAllTests() {
    console.log('🚀 Starting Comprehensive Integration Testing Suite');
    console.log('=' .repeat(80));
    console.log('Phase: Integration Testing & Validation');
    console.log('Focus: Production readiness for advanced search functionality');
    console.log('=' .repeat(80));
    
    // Test suites to run
    const testSuites = [
      {
        name: 'Unit Tests',
        command: 'npm run test -- --passWithNoTests',
        description: 'Basic unit tests for components and utilities',
      },
      {
        name: 'Integration Tests',
        command: 'npm run test:integration',
        description: 'Search functionality with real data validation',
      },
      {
        name: 'Security Tests',
        command: 'npm run test:security',
        description: 'Admin authentication and security measures',
      },
      {
        name: 'Edge Case Tests',
        command: 'npm run test -- --testPathPattern=edge-cases',
        description: 'Error handling and malformed data scenarios',
      },
    ];
    
    // Run each test suite
    for (const suite of testSuites) {
      await this.runTestSuite(suite.name, suite.command, suite.description);
    }
    
    // Run performance tests
    await this.runPerformanceTests();
    
    // Note about E2E tests
    console.log('\\n📝 Note: E2E Tests require manual execution');
    console.log('   Run: npm run test:e2e (requires dev server running)');
    
    // Calculate production readiness
    const score = this.calculateProductionReadiness();
    
    // Generate reports
    await this.generateReport();
    
    console.log('\\n' + '='.repeat(80));
    console.log('🎯 INTEGRATION TESTING COMPLETE');
    console.log('=' .repeat(80));
    console.log(`Production Readiness Score: ${score}/100`);
    console.log('\\nNext Steps:');
    console.log('1. Review generated reports (TESTING_REPORT.md, PRODUCTION_READINESS.md)');
    console.log('2. Address any failing tests or recommendations');
    console.log('3. Run E2E tests manually with: npm run test:e2e');
    console.log('4. Consider production deployment when score >= 90');
    console.log('=' .repeat(80));
    
    return score;
  }
}

// Run tests if called directly
if (require.main === module) {
  const runner = new IntegrationTestRunner();
  runner.runAllTests().catch(console.error);
}

module.exports = IntegrationTestRunner;

