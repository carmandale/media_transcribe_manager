curl https://api.x.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer xai-yjH0MunMCgaboncKPHy4WAwF3epuDrTLKAGGLfdXQN1V2wmEPNjWf5cKTf54cMyBJmMKJNl1F6KgqIbj" \
  -d '{
  "messages": [
    {
      "role": "system",
      "content": "You are a test assistant."
    },
    {
      "role": "user",
      "content": "Testing. Just say hi and hello world and nothing else."
    }
  ],
  "model": "grok-3-latest",
  "stream": false,
  "temperature": 0
}'