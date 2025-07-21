import '@testing-library/jest-dom'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
      forward: jest.fn(),
      refresh: jest.fn(),
    }
  },
  useSearchParams() {
    return new URLSearchParams()
  },
  usePathname() {
    return '/'
  },
}))

// Mock Next.js server components
jest.mock('next/server', () => ({
  NextRequest: class MockNextRequest {
    constructor(url, options = {}) {
      this._url = url
      this.method = options.method || 'GET'
      this.headers = options.headers instanceof Headers ? options.headers : new Headers(options.headers)
      this.body = options.body
    }
    
    get url() {
      return this._url
    }
  },
  NextResponse: {
    json: (data, options = {}) => {
      const response = new Response(JSON.stringify(data), {
        status: options.status || 200,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      })
      return response
    }
  }
}))

// Mock environment variables for testing
process.env.NODE_ENV = 'test'
process.env.ADMIN_API_KEY = 'test-api-key-for-testing'

// Global test utilities
global.fetch = jest.fn()

// Mock Web APIs for Next.js environment
if (typeof global.Request === 'undefined') {
  global.Request = class MockRequest {
    constructor(url, options = {}) {
      this._url = url
      this.method = options.method || 'GET'
      this.headers = options.headers instanceof Headers ? options.headers : new Headers(options.headers)
      this.body = options.body
    }
    
    get url() {
      return this._url
    }
  }
}

if (typeof global.Response === 'undefined') {
  global.Response = class MockResponse {
    constructor(body, options = {}) {
      this.body = body
      this.status = options.status || 200
      this.statusText = options.statusText || 'OK'
      this.headers = new Headers(options.headers)
    }
    
    async json() {
      return typeof this.body === 'string' ? JSON.parse(this.body) : this.body
    }
    
    async text() {
      return typeof this.body === 'string' ? this.body : JSON.stringify(this.body)
    }
  }
}

if (typeof global.Headers === 'undefined') {
  global.Headers = class MockHeaders {
    constructor(init = {}) {
      this.map = new Map()
      if (init) {
        Object.entries(init).forEach(([key, value]) => {
          this.map.set(key.toLowerCase(), value)
        })
      }
    }
    
    get(name) {
      return this.map.get(name.toLowerCase())
    }
    
    set(name, value) {
      this.map.set(name.toLowerCase(), value)
    }
    
    has(name) {
      return this.map.has(name.toLowerCase())
    }
    
    delete(name) {
      this.map.delete(name.toLowerCase())
    }
    
    entries() {
      return this.map.entries()
    }
    
    forEach(callback) {
      this.map.forEach((value, key) => callback(value, key, this))
    }
  }
}

// Ensure URL and URLSearchParams are available (Node.js built-ins)
if (typeof global.URL === 'undefined') {
  const { URL, URLSearchParams } = require('url')
  global.URL = URL
  global.URLSearchParams = URLSearchParams
}

// Setup for performance testing
global.performance = global.performance || {
  now: jest.fn(() => Date.now()),
  mark: jest.fn(),
  measure: jest.fn(),
}

// Console error suppression for expected errors in tests
const originalError = console.error
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render is no longer supported')
    ) {
      return
    }
    originalError.call(console, ...args)
  }
})

afterAll(() => {
  console.error = originalError
})
