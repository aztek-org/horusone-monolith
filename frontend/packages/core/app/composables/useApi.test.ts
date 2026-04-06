import { describe, it, expect, vi, beforeEach } from 'vitest'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock Nuxt's useRuntimeConfig (resolved via auto-import from #app/nuxt)
vi.mock('#app/nuxt', () => ({
  useRuntimeConfig: vi.fn(() => ({
    public: {
      apiUrl: 'http://localhost:8000',
      wsUrl: 'ws://localhost:8000/ws/voice',
    },
  })),
}))

// Mock useAuth (auto-imported from the sibling composable)
const mockGetAccessToken = vi.fn().mockResolvedValue('test-access-token')
const mockIsAuthenticated = { value: true }

vi.mock('./useAuth', () => ({
  useAuth: vi.fn(() => ({
    getAccessToken: mockGetAccessToken,
    isAuthenticated: mockIsAuthenticated,
  })),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetchOk<T>(body: T, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status,
    json: () => Promise.resolve(body),
  })
}

function mockFetchError(status: number, body?: { detail?: string }) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: body ? () => Promise.resolve(body) : () => Promise.reject(new Error('no body')),
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    // Restore default mock behaviours after clearAllMocks wipes implementations
    mockGetAccessToken.mockResolvedValue('test-access-token')
    mockIsAuthenticated.value = true
  })

  // -- HTTP methods ---------------------------------------------------------

  it('get() sends a GET request with Authorization header', async () => {
    const fetchMock = mockFetchOk({ items: [1, 2, 3] })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    const result = await useApi().get<{ items: number[] }>('/api/v1/items')

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/items')
    expect(opts.method).toBe('GET')
    expect((opts.headers as Record<string, string>).Authorization).toBe(
      'Bearer test-access-token',
    )
    expect(result).toEqual({ items: [1, 2, 3] })
  })

  it('post() sends a POST request with a JSON-stringified body', async () => {
    const fetchMock = mockFetchOk({ id: 'new-1' })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    const payload = { name: 'Cross-wind Landing' }
    const result = await useApi().post<{ id: string }>('/api/v1/scenarios', payload)

    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(opts.method).toBe('POST')
    expect(opts.body).toBe(JSON.stringify(payload))
    expect((opts.headers as Record<string, string>)['Content-Type']).toBe(
      'application/json',
    )
    expect(result).toEqual({ id: 'new-1' })
  })

  it('put() sends a PUT request with a JSON-stringified body', async () => {
    const fetchMock = mockFetchOk({ updated: true })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    await useApi().put('/api/v1/scenarios/1', { name: 'Revised' })

    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/scenarios/1')
    expect(opts.method).toBe('PUT')
    expect(opts.body).toBe(JSON.stringify({ name: 'Revised' }))
  })

  it('del() sends a DELETE request', async () => {
    const fetchMock = mockFetchOk(undefined, 204)
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    await useApi().del('/api/v1/scenarios/1')

    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/scenarios/1')
    expect(opts.method).toBe('DELETE')
  })

  // -- Auth header behaviour ------------------------------------------------

  it('request() skips the auth header when noAuth is true', async () => {
    const fetchMock = mockFetchOk({ status: 'ok' })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    await useApi().get('/api/v1/health', { noAuth: true })

    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((opts.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('request() skips the auth header when not authenticated', async () => {
    mockIsAuthenticated.value = false
    const fetchMock = mockFetchOk({ public: true })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    await useApi().get('/api/v1/public')

    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((opts.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('request() skips the auth header when getAccessToken returns null', async () => {
    mockGetAccessToken.mockResolvedValue(null)
    const fetchMock = mockFetchOk({ data: 'none' })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')
    await useApi().get('/api/v1/items')

    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((opts.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  // -- Error handling -------------------------------------------------------

  it('request() throws an ApiError with detail from the response body', async () => {
    const fetchMock = mockFetchError(422, { detail: 'Validation error: name required' })
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')

    await expect(useApi().get('/api/v1/items')).rejects.toEqual({
      status: 422,
      detail: 'Validation error: name required',
    })
  })

  it('request() throws an ApiError with a default message when body parsing fails', async () => {
    const fetchMock = mockFetchError(500)
    vi.stubGlobal('fetch', fetchMock)

    const { useApi } = await import('./useApi')

    await expect(useApi().post('/api/v1/items', {})).rejects.toEqual({
      status: 500,
      detail: 'Request failed: 500',
    })
  })

  // -- 204 No Content -------------------------------------------------------

  it('request() returns undefined for a 204 No Content response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 204 }),
    )

    const { useApi } = await import('./useApi')
    const result = await useApi().del('/api/v1/items/99')

    expect(result).toBeUndefined()
  })

  // -- WebSocket URL --------------------------------------------------------

  it('getAuthenticatedWsUrl() returns the base wsUrl with a token param', async () => {
    const { useApi } = await import('./useApi')
    const url = await useApi().getAuthenticatedWsUrl()

    expect(url).toBe('ws://localhost:8000/ws/voice?token=test-access-token')
  })

  it('getAuthenticatedWsUrl() uses a custom path when provided', async () => {
    const { useApi } = await import('./useApi')
    const url = await useApi().getAuthenticatedWsUrl('/ws/atc')

    expect(url).toBe('ws://localhost:8000/ws/atc?token=test-access-token')
  })

  it('getAuthenticatedWsUrl() omits the token param when getAccessToken returns null', async () => {
    mockGetAccessToken.mockResolvedValue(null)

    const { useApi } = await import('./useApi')
    const url = await useApi().getAuthenticatedWsUrl()

    expect(url).toBe('ws://localhost:8000/ws/voice')
  })
})
