import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock Nuxt's useRuntimeConfig (resolved via auto-import from #app/nuxt)
vi.mock('#app/nuxt', () => ({
  useRuntimeConfig: vi.fn(() => ({
    public: {
      keycloakUrl: 'http://localhost:8180',
      keycloakRealm: 'horus',
      keycloakClientId: 'horus-web',
    },
  })),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal JWT (header.payload.signature) that parseJwtPayload can decode. */
function createTestJwt(
  claims: Record<string, unknown>,
  expiresInSeconds = 3600,
): string {
  const header = { alg: 'RS256', typ: 'JWT' }
  const now = Math.floor(Date.now() / 1000)
  const payload = { iat: now, exp: now + expiresInSeconds, ...claims }
  const encode = (obj: unknown) =>
    btoa(JSON.stringify(obj))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
  return `${encode(header)}.${encode(payload)}.fake-signature`
}

const defaultClaims = {
  sub: 'user-123',
  email: 'pilot@horus.app',
  preferred_username: 'maverick',
  realm_access: { roles: ['student', 'pilot'] },
  organization_id: 'org-456',
}

function createMockSessionStorage() {
  const store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, val: string) => { store[key] = val }),
    removeItem: vi.fn((key: string) => { Reflect.deleteProperty(store, key) }),
    clear: vi.fn(() => { for (const k of Object.keys(store)) Reflect.deleteProperty(store, k) }),
    /** Direct access to the backing store for test setup */
    _store: store,
  }
}

function createMockLocation(overrides: Record<string, string> = {}) {
  const origin = overrides.origin ?? 'http://localhost:3000'
  const pathname = overrides.pathname ?? '/auth/callback'
  const search = overrides.search ?? ''

  return {
    origin,
    pathname,
    search,
    href: overrides.href ?? `${origin}${pathname}${search}`,
    ...overrides,
  }
}

function createMockFetchTokenResponse(jwt: string) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        access_token: jwt,
        refresh_token: 'refresh-token-abc',
        expires_in: 300,
      }),
  })
}

/**
 * Convenience: authenticate via handleCallback so the module-level state
 * (user, accessToken, refreshTokenValue) is populated. Returns the auth API.
 */
async function authenticateWith(
  jwt: string,
  code = 'code-123',
) {
  const storage = createMockSessionStorage()
  storage._store['pkce_code_verifier'] = 'test-verifier'
  vi.stubGlobal('sessionStorage', storage)
  vi.stubGlobal('location', createMockLocation({ search: `?code=${code}` }))
  vi.stubGlobal('fetch', createMockFetchTokenResponse(jwt))

  const { useAuth } = await import('./useAuth')
  const auth = useAuth()
  await auth.handleCallback()
  return auth
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    // Suppress console.error from handleCallback catch blocks
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  // -- Initial state --------------------------------------------------------

  it('initializes with null user and isLoading false after bootstrap', async () => {
    const { useAuth } = await import('./useAuth')
    const auth = useAuth()

    expect(auth.user.value).toBeNull()
    expect(auth.isLoading.value).toBe(false)
    expect(auth.error.value).toBeNull()
    expect(auth.accessToken.value).toBeNull()
  })

  it('isAuthenticated is false when no token or user exists', async () => {
    const { useAuth } = await import('./useAuth')
    const auth = useAuth()

    expect(auth.isAuthenticated.value).toBe(false)
  })

  // -- login() --------------------------------------------------------------

  it('login() stores a base64url-safe PKCE code verifier in sessionStorage', async () => {
    const storage = createMockSessionStorage()
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation())

    const { useAuth } = await import('./useAuth')
    useAuth().login()

    expect(storage.setItem).toHaveBeenCalledWith(
      'pkce_code_verifier',
      expect.any(String),
    )

    const verifier = storage.setItem.mock.calls[0]![1] as string
    // base64url alphabet only — no +, /, or = characters
    expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(verifier.length).toBeGreaterThan(0)
  })

  it('login() stores the redirect path when one is provided', async () => {
    const storage = createMockSessionStorage()
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation())

    const { useAuth } = await import('./useAuth')
    useAuth().login('/org/dashboard')

    expect(storage.setItem).toHaveBeenCalledWith('auth_redirect', '/org/dashboard')
  })

  it('login() does not store a redirect path when none is provided', async () => {
    const storage = createMockSessionStorage()
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation())

    const { useAuth } = await import('./useAuth')
    useAuth().login()

    const setItemCalls = storage.setItem.mock.calls.map(
      (c: [string, string]) => c[0],
    )
    expect(setItemCalls).not.toContain('auth_redirect')
  })

  it('login() redirects to the Keycloak auth endpoint with correct params', async () => {
    const loc = createMockLocation()
    vi.stubGlobal('sessionStorage', createMockSessionStorage())
    vi.stubGlobal('location', loc)

    const { useAuth } = await import('./useAuth')
    useAuth().login()

    // login() is fire-and-forget: generateCodeChallenge().then(…)
    await vi.waitFor(() => {
      expect(loc.href).toContain(
        'http://localhost:8180/realms/horus/protocol/openid-connect/auth?',
      )
    })

    const url = new URL(loc.href)
    expect(url.searchParams.get('client_id')).toBe('horus-web')
    expect(url.searchParams.get('response_type')).toBe('code')
    expect(url.searchParams.get('scope')).toBe('openid email profile')
    expect(url.searchParams.get('redirect_uri')).toBe(
      'http://localhost:3000/auth/callback',
    )
    expect(url.searchParams.get('code_challenge_method')).toBe('S256')
    expect(url.searchParams.get('code_challenge')).toBeTruthy()
    expect(url.searchParams.get('state')).toBeTruthy()
  })

  it('login() refuses on an insecure origin instead of throwing', async () => {
    const storage = createMockSessionStorage()
    const loc = createMockLocation()
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', loc)

    // crypto.subtle is unavailable in an insecure context; simulate the browser
    // reporting it via the standard isSecureContext flag.
    const win = window as unknown as Record<string, unknown>
    const hadOwn = Object.prototype.hasOwnProperty.call(win, 'isSecureContext')
    const previous = win.isSecureContext
    win.isSecureContext = false
    try {
      const { useAuth } = await import('./useAuth')
      const auth = useAuth()
      auth.login()

      expect(auth.error.value).toMatch(/HTTPS/i)
      expect(storage.setItem).not.toHaveBeenCalled()
      expect(loc.href).toBe('http://localhost:3000/auth/callback')
    }
    finally {
      if (hadOwn) win.isSecureContext = previous
      else Reflect.deleteProperty(win, 'isSecureContext')
    }
  })

  // -- handleCallback() -----------------------------------------------------

  it('handleCallback() exchanges the authorization code for tokens via POST', async () => {
    const jwt = createTestJwt(defaultClaims)
    const fetchMock = createMockFetchTokenResponse(jwt)
    const storage = createMockSessionStorage()
    storage._store['pkce_code_verifier'] = 'my-verifier'

    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation({ search: '?code=auth-code-42' }))

    const { useAuth } = await import('./useAuth')
    await useAuth().handleCallback()

    expect(fetchMock).toHaveBeenCalled()
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(
      'http://localhost:8180/realms/horus/protocol/openid-connect/token',
    )
    expect(opts.method).toBe('POST')

    const body = (opts.body as URLSearchParams).toString()
    expect(body).toContain('grant_type=authorization_code')
    expect(body).toContain('code=auth-code-42')
    expect(body).toContain('code_verifier=my-verifier')
    expect(body).toContain('client_id=horus-web')
  })

  it('handleCallback() populates user from JWT claims', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)

    expect(auth.user.value).toEqual({
      keycloakId: 'user-123',
      email: 'pilot@horus.app',
      displayName: 'maverick',
      roles: ['student', 'pilot'],
      organizationId: 'org-456',
    })
    expect(auth.accessToken.value).toBe(jwt)
    expect(auth.isAuthenticated.value).toBe(true)
    expect(auth.error.value).toBeNull()
  })

  it('handleCallback() handles minimal JWT claims gracefully', async () => {
    const minimalClaims = { sub: 'user-min' }
    const jwt = createTestJwt(minimalClaims)
    const auth = await authenticateWith(jwt)

    expect(auth.user.value).toEqual({
      keycloakId: 'user-min',
      email: '',
      displayName: '',
      roles: [],
      organizationId: null,
    })
  })

  it('handleCallback() removes the PKCE verifier from sessionStorage', async () => {
    const jwt = createTestJwt(defaultClaims)
    const storage = createMockSessionStorage()
    storage._store['pkce_code_verifier'] = 'v'

    vi.stubGlobal('fetch', createMockFetchTokenResponse(jwt))
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation({ search: '?code=c' }))

    const { useAuth } = await import('./useAuth')
    await useAuth().handleCallback()

    expect(storage.removeItem).toHaveBeenCalledWith('pkce_code_verifier')
  })

  it('handleCallback() sets error when the authorization code is missing', async () => {
    vi.stubGlobal('sessionStorage', createMockSessionStorage())
    vi.stubGlobal('location', createMockLocation({ search: '' }))

    const { useAuth } = await import('./useAuth')
    const auth = useAuth()
    await auth.handleCallback()

    expect(auth.error.value).toBe(
      'Missing authorization code or PKCE verifier',
    )
    expect(auth.user.value).toBeNull()
  })

  it('handleCallback() sets error when the PKCE verifier is missing', async () => {
    vi.stubGlobal('sessionStorage', createMockSessionStorage()) // empty store
    vi.stubGlobal('location', createMockLocation({ search: '?code=abc' }))

    const { useAuth } = await import('./useAuth')
    const auth = useAuth()
    await auth.handleCallback()

    expect(auth.error.value).toBe(
      'Missing authorization code or PKCE verifier',
    )
  })

  it('handleCallback() sets error on HTTP failure from token endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400 }))

    const storage = createMockSessionStorage()
    storage._store['pkce_code_verifier'] = 'v'
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation({ search: '?code=bad' }))

    const { useAuth } = await import('./useAuth')
    const auth = useAuth()
    await auth.handleCallback()

    expect(auth.error.value).toBe('Token exchange failed: 400')
    expect(auth.user.value).toBeNull()
  })

  it('handleCallback() sets error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const storage = createMockSessionStorage()
    storage._store['pkce_code_verifier'] = 'v'
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation({ search: '?code=x' }))

    const { useAuth } = await import('./useAuth')
    const auth = useAuth()
    await auth.handleCallback()

    expect(auth.error.value).toBe('Failed to fetch')
    expect(auth.user.value).toBeNull()
  })

  it('handleCallback() always sets isLoading to false when finished', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    const storage = createMockSessionStorage()
    storage._store['pkce_code_verifier'] = 'v'
    vi.stubGlobal('sessionStorage', storage)
    vi.stubGlobal('location', createMockLocation({ search: '?code=x' }))

    const { useAuth } = await import('./useAuth')
    const auth = useAuth()
    await auth.handleCallback()

    // Even on failure, isLoading must be false
    expect(auth.isLoading.value).toBe(false)
  })

  // -- logout() -------------------------------------------------------------

  it('logout() clears user, token, and sets isAuthenticated to false', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)
    expect(auth.isAuthenticated.value).toBe(true)

    auth.logout()

    expect(auth.user.value).toBeNull()
    expect(auth.accessToken.value).toBeNull()
    expect(auth.isAuthenticated.value).toBe(false)
  })

  it('logout() redirects to the Keycloak logout endpoint', async () => {
    const loc = createMockLocation()
    vi.stubGlobal('location', loc)

    const { useAuth } = await import('./useAuth')
    useAuth().logout()

    expect(loc.href).toContain(
      'http://localhost:8180/realms/horus/protocol/openid-connect/logout?',
    )
    const url = new URL(loc.href)
    expect(url.searchParams.get('client_id')).toBe('horus-web')
    expect(url.searchParams.get('post_logout_redirect_uri')).toBe(
      'http://localhost:3000/login',
    )
  })

  // -- refreshToken() -------------------------------------------------------

  it('refreshToken() returns false when no refresh token exists', async () => {
    const { useAuth } = await import('./useAuth')
    const result = await useAuth().refreshToken()

    expect(result).toBe(false)
  })

  it('refreshToken() obtains new tokens on success', async () => {
    const jwt1 = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt1)

    const jwt2 = createTestJwt({ ...defaultClaims, email: 'refreshed@horus.app' })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            access_token: jwt2,
            refresh_token: 'new-refresh',
            expires_in: 600,
          }),
      }),
    )

    const result = await auth.refreshToken()

    expect(result).toBe(true)
    expect(auth.accessToken.value).toBe(jwt2)
    expect(auth.user.value?.email).toBe('refreshed@horus.app')
  })

  it('refreshToken() clears auth state and returns false on failure', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)
    expect(auth.isAuthenticated.value).toBe(true)

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))

    const result = await auth.refreshToken()

    expect(result).toBe(false)
    expect(auth.user.value).toBeNull()
    expect(auth.accessToken.value).toBeNull()
    expect(auth.isAuthenticated.value).toBe(false)
  })

  // -- getAccessToken() -----------------------------------------------------

  it('getAccessToken() returns null when no token exists', async () => {
    const { useAuth } = await import('./useAuth')
    const token = await useAuth().getAccessToken()

    expect(token).toBeNull()
  })

  it('getAccessToken() returns the token when it is not near expiry', async () => {
    const jwt = createTestJwt(defaultClaims, 3600) // 1 hour
    const auth = await authenticateWith(jwt)

    const token = await auth.getAccessToken()

    expect(token).toBe(jwt)
  })

  it('getAccessToken() triggers a refresh when the token is near expiry', async () => {
    // Token that expires in 10 s (below the 30 s threshold)
    const nearExpiryJwt = createTestJwt(defaultClaims, 10)
    const auth = await authenticateWith(nearExpiryJwt)

    const freshJwt = createTestJwt(defaultClaims, 3600)
    const refreshFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          access_token: freshJwt,
          refresh_token: 'new-refresh',
          expires_in: 3600,
        }),
    })
    vi.stubGlobal('fetch', refreshFetch)

    const token = await auth.getAccessToken()

    expect(refreshFetch).toHaveBeenCalled()
    expect(token).toBe(freshJwt)
  })

  it('getAccessToken() returns null when refresh fails for a near-expiry token', async () => {
    const nearExpiryJwt = createTestJwt(defaultClaims, 5)
    const auth = await authenticateWith(nearExpiryJwt)

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))

    const token = await auth.getAccessToken()

    expect(token).toBeNull()
  })

  // -- hasRole() / hasAnyRole() ---------------------------------------------

  it('hasRole() returns true for a role the user has', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)

    expect(auth.hasRole('student')).toBe(true)
    expect(auth.hasRole('pilot')).toBe(true)
  })

  it('hasRole() returns false for a role the user does not have', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)

    expect(auth.hasRole('org-admin')).toBe(false)
  })

  it('hasRole() returns false when user is null', async () => {
    vi.stubGlobal('sessionStorage', createMockSessionStorage())
    const { useAuth } = await import('./useAuth')

    expect(useAuth().hasRole('student')).toBe(false)
  })

  it('hasAnyRole() returns true when at least one role matches', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)

    expect(auth.hasAnyRole('org-admin', 'student')).toBe(true)
  })

  it('hasAnyRole() returns false when no roles match', async () => {
    const jwt = createTestJwt(defaultClaims)
    const auth = await authenticateWith(jwt)

    expect(auth.hasAnyRole('org-admin', 'superadmin')).toBe(false)
  })
})
