type HorusAppId = 'hangar' | 'tower' | 'squawk'

const FALLBACK_ROUTES: Record<HorusAppId, string> = {
  hangar: '/dashboard',
  tower: '/dashboard',
  squawk: '/dashboard',
}

const DISALLOWED_REDIRECT_PREFIXES = ['/login', '/auth/callback']

function normalizeAppId(value: unknown): HorusAppId {
  if (value === 'tower' || value === 'squawk' || value === 'hangar') {
    return value
  }
  return 'hangar'
}

function normalizeBaseUrl(value: unknown, fallback: string): string {
  const source = typeof value === 'string' && value.trim() ? value.trim() : fallback

  try {
    const url = new URL(source)
    url.pathname = url.pathname === '/' ? '' : url.pathname.replace(/\/+$/, '')
    url.search = ''
    url.hash = ''
    return url.toString().replace(/\/$/, '')
  }
  catch {
    return fallback
  }
}

function normalizePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`
}

export function useAuthRouting() {
  const config = useRuntimeConfig()
  const router = useRouter()

  const hangarUrl = normalizeBaseUrl(config.public.hangarUrl, 'http://localhost:3002')
  const towerUrl = normalizeBaseUrl(config.public.towerUrl, 'http://localhost:3001')
  const squawkUrl = normalizeBaseUrl(config.public.squawkUrl, 'http://localhost:3000')
  const currentApp = normalizeAppId(config.public.appId)
  const authGatewayUrl = normalizeBaseUrl(config.public.authGatewayUrl, hangarUrl)

  const appUrls: Record<HorusAppId, string> = {
    hangar: hangarUrl,
    tower: towerUrl,
    squawk: squawkUrl,
  }

  function getFallbackRoute(app: HorusAppId = currentApp): string {
    return FALLBACK_ROUTES[app]
  }

  function resolveTargetApp(roles: string[]): HorusAppId {
    if (roles.includes('platform-admin')) return 'squawk'
    if (roles.includes('org-admin') || roles.includes('instructor')) return 'tower'
    return 'hangar'
  }

  function isCurrentApp(app: HorusAppId): boolean {
    return currentApp === app
  }

  function resolveSafeRedirect(
    rawRedirect: unknown,
    targetApp: HorusAppId = currentApp,
  ): string {
    const fallback = getFallbackRoute(targetApp)

    if (typeof rawRedirect !== 'string' || !rawRedirect.startsWith('/')) {
      return fallback
    }

    if (DISALLOWED_REDIRECT_PREFIXES.some(prefix => rawRedirect.startsWith(prefix))) {
      return fallback
    }

    if (targetApp !== currentApp) {
      return rawRedirect
    }

    const resolved = router.resolve(rawRedirect)
    return resolved.matched.length > 0 ? rawRedirect : fallback
  }

  function buildAppUrl(
    app: HorusAppId,
    path: string,
    query?: Record<string, string | null | undefined>,
  ): string {
    const url = new URL(appUrls[app])
    url.pathname = normalizePath(path)
    url.search = ''

    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') return
        url.searchParams.set(key, value)
      })
    }

    return url.toString()
  }

  function buildGatewayLoginUrl(redirectPath: string): string {
    const url = new URL('/login', authGatewayUrl)
    url.searchParams.set('redirect', redirectPath)
    return url.toString()
  }

  function shouldRedirectToGatewayLogin(isHandoff: boolean): boolean {
    if (import.meta.server || isHandoff) return false

    try {
      const gatewayOrigin = new URL(authGatewayUrl).origin
      return window.location.origin !== gatewayOrigin
    }
    catch {
      return false
    }
  }

  return {
    currentApp,
    authGatewayUrl,
    getFallbackRoute,
    resolveTargetApp,
    isCurrentApp,
    resolveSafeRedirect,
    buildAppUrl,
    buildGatewayLoginUrl,
    shouldRedirectToGatewayLogin,
  }
}
