# Admin Authentication Setup

## Overview

The admin panel and API routes are protected with basic API key authentication to prevent unauthorized access to interview management functionality.

## Environment Variables

Add the following environment variable to your `.env.local` file:

```bash
# Admin API Key for accessing admin routes
ADMIN_API_KEY=your-secure-api-key-here
```

## Development Mode

In development mode (NODE_ENV=development), if no `ADMIN_API_KEY` is set, the system will allow access with a default development user. This is for convenience during development only.

## Production Setup

**IMPORTANT**: In production, you MUST set a secure `ADMIN_API_KEY` environment variable.

1. Generate a secure API key (recommended: 32+ character random string)
2. Set the `ADMIN_API_KEY` environment variable in your production environment
3. Use this API key when making requests to admin endpoints

## Using the API Key

### Option 1: Authorization Header (Recommended)
```bash
curl -H "Authorization: Bearer your-api-key-here" \
  https://your-domain.com/api/admin/interviews
```

### Option 2: Query Parameter
```bash
curl "https://your-domain.com/api/admin/interviews?api_key=your-api-key-here"
```

## Admin Panel Access

The admin panel at `/admin` will automatically include the API key in requests when you're authenticated. The authentication is handled transparently by the frontend.

## Security Notes

- API keys should be treated as sensitive credentials
- Never commit API keys to version control
- Rotate API keys regularly in production
- Consider implementing more sophisticated authentication (OAuth, JWT) for production use
- The current implementation is a basic security measure suitable for internal tools

## Future Enhancements

This basic API key authentication can be enhanced with:
- User management and role-based access control
- JWT tokens with expiration
- OAuth integration
- Audit logging of admin actions
- Rate limiting and request throttling

