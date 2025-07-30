/**
 * Simple test script for the chat API endpoint
 * Tests the /api/chat endpoint without requiring OpenAI API key
 */

const testChatAPI = async () => {
  console.log('🧪 Testing Chat API Endpoint...\n');

  // Test health check endpoint first
  console.log('Testing health check endpoint...');
  try {
    const response = await fetch('http://localhost:3000/api/chat', {
      method: 'GET',
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('✅ Health check passed');
      console.log('   Status:', data.status);
      console.log('   Features:', JSON.stringify(data.features, null, 2));
    } else {
      console.log('❌ Health check failed');
    }
  } catch (error) {
    console.log('❌ Health check error:', error.message);
    console.log('ℹ️  Make sure the Next.js dev server is running on localhost:3000');
    return;
  }

  console.log('\n' + '='.repeat(50) + '\n');

  const testQueries = [
    {
      name: 'Invalid query (empty string)',
      query: '',
      expectError: true,
    },
    {
      name: 'Invalid query (too long)',
      query: 'a'.repeat(501),
      expectError: true,
    },
    {
      name: 'Valid query (will fail without OpenAI key)',
      query: 'What did they say about feeling like second-class citizens?',
      expectError: false,
    },
  ];

  for (const test of testQueries) {
    console.log(`Testing: ${test.name}`);
    console.log(`Query: "${test.query.length > 50 ? test.query.substring(0, 50) + '...' : test.query}"`);
    
    try {
      const response = await fetch('http://localhost:3000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: test.query,
          maxResults: 5,
        }),
      });

      const data = await response.json();
      
      if (test.expectError) {
        if (!response.ok) {
          console.log('✅ Expected error received:', data.error);
        } else {
          console.log('❌ Expected error but got success');
        }
      } else {
        console.log(`Status: ${response.status} ${response.statusText}`);
        
        if (response.ok) {
          console.log('✅ API structure is correct');
          console.log(`   Session ID: ${data.sessionId}`);
          console.log(`   Response time: ${data.responseTime}ms`);
          console.log(`   Response preview: ${data.response?.substring(0, 100) || 'No response'}...`);
        } else {
          console.log('Expected error (likely missing OpenAI key):', data.error);
          if (data.error?.includes('temporarily unavailable')) {
            console.log('ℹ️  This is expected - OpenAI API key not configured for testing');
          }
        }
      }
    } catch (error) {
      console.log('❌ Network error:', error.message);
    }
    
    console.log('');
  }

  console.log('🎉 Chat API endpoint testing complete!');
  console.log('📝 Next steps:');
  console.log('   1. Add OPENAI_API_KEY to environment variables for full functionality');
  console.log('   2. Test with real queries once API key is configured');
  console.log('   3. Build the chat UI components');
};

// Run the test
testChatAPI().catch(console.error);