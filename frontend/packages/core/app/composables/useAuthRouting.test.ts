import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockConfig = {
  public: {
    hangarUrl: 'http://localhost:3002/',
    towerUrl: 'http://localhost:3001',
    squawkUrl: 'http://localhost:3000',
    appId: 'hangar',
    authGatewayUrl: 'http://localhost:3002',
  } as Record<string, unknown>,
}

const mockResolve = vi.fn(() => ({ matched: [] as unknown[] }))

vi.mock('#app/nuxt', () => ({
  useRuntimeConfig: () => mockConfig,
}))

vi.mock('#app/composables/router', () => ({
  useRouter: () => ({ resolve: mockResolve }),
}))

async function setup() {
  const { useAuthRouting } = await import('./useAuthRouting')
  return useAuthRouting()
}

function resetConfig() {
  mockConfig.public = {
    hangarUrl: 'http://localhost:3002/',
    towerUrl: 'http://localhost:3001',
    squawkUrl: 'http://localhost:3000',
    appId: 'hangar',
    authGatewayUrl: 'http://localhost:3002',
  }
}

describe('useAuthRouting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockResolve.mockReturnValue({ matched: [] })
    resetConfig()
  })

  // -- currentApp / fallbacks ----------------------------------------------
  it('normalizes the configured app id', async () => {
    expect((await setup()).currentApp).toBe('hangar')
    mockConfig.public = { ...mockConfig.public, appId: 'tower' }
    expect((await setup()).currentApp).toBe('tower')
  })

  it('falls back to hangar for an unknown app id', async () => {
    mockConfig.public = { ...mockConfig.public, appId: 'unknown-app' }
    expect((await setup()).currentApp).toBe('hangar')
  })

  it('getFallbackRoute returns the app dashboard for every app', async () => {
    const routing = await setup()
    expect(routing.getFallbackRoute('hangar')).toBe('/dashboard')
    expect(routing.getFallbackRoute('tower')).toBe('/dashboard')
    expect(routing.getFallbackRoute('squawk')).toBe('/dashboard')
  })

  // -- resolveTargetApp -----------------------------------------------------
  it('resolveTargetApp maps roles to the appropriate app', async () => {
    const routing = await setup()
    expect(routing.resolveTargetApp(['platform-admin'])).toBe('squawk')
    expect(routing.resolveTargetApp(['org-admin'])).toBe('tower')
    expect(routing.resolveTargetApp(['instructor'])).toBe('tower')
    expect(routing.resolveTargetApp(['student', 'pilot'])).toBe('hangar')
    expect(routing.resolveTargetApp([])).toBe('hangar')
  })

  it('isCurrentApp compares against the configured app', async () => {
    const routing = await setup()
    expect(routing.isCurrentApp('hangar')).toBe(true)
    expect(routing.isCurrentApp('tower')).toBe(false)
  })

  // -- buildAppUrl ----------------------------------------------------------
  it('buildAppUrl normalizes the base url and path', async () => {
    const routing = await setup()
    expect(routing.buildAppUrl('hangar', 'dashboard')).toBe('http://localhost:3002/dashboard')
    expect(routing.buildAppUrl('tower', '/settings')).toBe('http://localhost:3001/settings')
  })

  it('buildAppUrl appends non-empty query params only', async () => {
    const routing = await setup()
    const url = routing.buildAppUrl('hangar', '/dashboard', {
      view: 'map',
      empty: '',
      skip: undefined,
      none: null,
    })
    expect(url).toBe('http://localhost:3002/dashboard?view=map')
  })

  it('buildGatewayLoginUrl points at the gateway login with a redirect param', async () => {
    const routing = await setup()
    expect(routing.buildGatewayLoginUrl('/org/dashboard')).toBe(
      'http://localhost:3002/login?redirect=%2Forg%2Fdashboard',
    )
  })

  // -- URL normalization ----------------------------------------------------
  it('strips trailing slashes and falls back for invalid URLs', async () => {
    const routing = await setup()
    expect(routing.authGatewayUrl).toBe('http://localhost:3002')

    mockConfig.public = { ...mockConfig.public, hangarUrl: 'not a url' }
    const fallback = await setup()
    expect(fallback.buildAppUrl('hangar', '/x')).toBe('http://localhost:3002/x')
  })

  // -- resolveSafeRedirect --------------------------------------------------
  it('resolveSafeRedirect returns the fallback for non-string or non-absolute input', async () => {
    const routing = await setup()
    expect(routing.resolveSafeRedirect(null)).toBe('/dashboard')
    expect(routing.resolveSafeRedirect('relative/path')).toBe('/dashboard')
    expect(routing.resolveSafeRedirect(undefined)).toBe('/dashboard')
  })

  it('resolveSafeRedirect rejects disallowed redirect prefixes', async () => {
    const routing = await setup()
    expect(routing.resolveSafeRedirect('/login')).toBe('/dashboard')
    expect(routing.resolveSafeRedirect('/auth/callback?code=1')).toBe('/dashboard')
  })

  it('resolveSafeRedirect passes through cross-app redirects', async () => {
    const routing = await setup()
    expect(routing.resolveSafeRedirect('/anything/here', 'tower')).toBe('/anything/here')
    expect(mockResolve).not.toHaveBeenCalled()
  })

  it('resolveSafeRedirect keeps same-app routes only when the router matches', async () => {
    const routing = await setup()
    mockResolve.mockReturnValue({ matched: [{}] })
    expect(routing.resolveSafeRedirect('/known-route')).toBe('/known-route')

    mockResolve.mockReturnValue({ matched: [] })
    expect(routing.resolveSafeRedirect('/unknown-route')).toBe('/dashboard')
  })

  // -- shouldRedirectToGatewayLogin -----------------------------------------
  it('shouldRedirectToGatewayLogin is false during a handoff', async () => {
    const routing = await setup()
    expect(routing.shouldRedirectToGatewayLogin(true)).toBe(false)
  })

  it('shouldRedirectToGatewayLogin is true when the origin differs from the gateway', async () => {
    const routing = await setup()
    // happy-dom default origin is http://localhost:3000; gateway is :3002
    expect(routing.shouldRedirectToGatewayLogin(false)).toBe(true)
  })

  it('shouldRedirectToGatewayLogin is false when the origin matches the gateway', async () => {
    mockConfig.public = { ...mockConfig.public, authGatewayUrl: 'http://localhost:3000' }
    const routing = await setup()
    expect(routing.shouldRedirectToGatewayLogin(false)).toBe(false)
  })
})
