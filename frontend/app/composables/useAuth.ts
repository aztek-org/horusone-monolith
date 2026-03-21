/**
 * Keycloak OIDC authentication composable.
 * Handles login, logout, token management, and user state via PKCE flow.
 */

interface AuthUser {
  keycloakId: string
  email: string
  displayName: string
  roles: string[]
  organizationId: string | null
}

interface SeatInfo {
  id: string
  organizationId: string
  organizationName: string | null
  role: string
  isActive: boolean
}

interface AuthState {
  user: Ref<AuthUser | null>
  isAuthenticated: Ref<boolean>
  isLoading: Ref<boolean>
  accessToken: Ref<string | null>
  error: Ref<string | null>
  hasActiveSeat: Ref<boolean>
  activeSeat: Ref<SeatInfo | null>
  seats: Ref<SeatInfo[]>
}

interface AuthActions {
  login: (redirectPath?: string) => void
  logout: () => Promise<void>
  handleCallback: () => Promise<void>
  refreshToken: () => Promise<boolean>
  getAccessToken: () => Promise<string | null>
  hasRole: (role: string) => boolean
  hasAnyRole: (...roles: string[]) => boolean
  fetchUserProfile: () => Promise<void>
}

// Module-level state (shared across components)
const user = ref<AuthUser | null>(null)
const accessToken = ref<string | null>(null)
const refreshTokenValue = ref<string | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const seats = ref<SeatInfo[]>([])
const hasActiveSeat = ref(false)
const activeSeat = ref<SeatInfo | null>(null)

let refreshTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Generate a random string for PKCE code verifier.
 */
function generateCodeVerifier(): string {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

/**
 * Generate PKCE code challenge from verifier using S256.
 */
async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(verifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

/**
 * Parse JWT token payload without verification (client-side only).
 */
function parseJwtPayload(token: string): Record<string, unknown> {
  const base64Url = token.split('.')[1]
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
  const payload = decodeURIComponent(
    atob(base64)
      .split('')
      .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
      .join(''),
  )
  return JSON.parse(payload)
}

/**
 * Extract AuthUser from JWT access token payload.
 */
function extractUser(payload: Record<string, unknown>): AuthUser {
  const realmAccess = (payload.realm_access as { roles?: string[] }) ?? {}

  return {
    keycloakId: (payload.sub as string) ?? '',
    email: (payload.email as string) ?? '',
    displayName:
      (payload.preferred_username as string) ?? (payload.name as string) ?? '',
    roles: realmAccess.roles ?? [],
    organizationId: (payload.organization_id as string) ?? null,
  }
}

export function useAuth(): AuthState & AuthActions {
  const config = useRuntimeConfig()
  const keycloakUrl = config.public.keycloakUrl as string
  const realm = config.public.keycloakRealm as string
  const clientId = config.public.keycloakClientId as string

  const baseUrl = `${keycloakUrl}/realms/${realm}/protocol/openid-connect`

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)

  /**
   * Redirect to Keycloak login page with PKCE.
   */
  function login(redirectPath?: string): void {
    if (import.meta.server) return

    const codeVerifier = generateCodeVerifier()
    sessionStorage.setItem('pkce_code_verifier', codeVerifier)

    if (redirectPath) {
      sessionStorage.setItem('auth_redirect', redirectPath)
    }

    generateCodeChallenge(codeVerifier).then((codeChallenge) => {
      const params = new URLSearchParams({
        client_id: clientId,
        response_type: 'code',
        scope: 'openid email profile',
        redirect_uri: `${window.location.origin}/auth/callback`,
        code_challenge: codeChallenge,
        code_challenge_method: 'S256',
        state: crypto.randomUUID(),
      })

      window.location.href = `${baseUrl}/auth?${params.toString()}`
    })
  }

  /**
   * Handle the OIDC callback — exchange code for tokens.
   */
  async function handleCallback(): Promise<void> {
    if (import.meta.server) return

    // Extract code from URL — use full href to avoid SSR hydration edge cases
    const callbackUrl = new URL(window.location.href)
    const code = callbackUrl.searchParams.get('code')
    const codeVerifier = sessionStorage.getItem('pkce_code_verifier')

    if (!code || !codeVerifier) {
      console.error('[useAuth] callback missing params:', {
        hasCode: !!code,
        hasVerifier: !!codeVerifier,
        href: window.location.href,
      })
      error.value = 'Missing authorization code or PKCE verifier'
      return
    }

    sessionStorage.removeItem('pkce_code_verifier')

    try {
      isLoading.value = true
      const response = await fetch(`${baseUrl}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: clientId,
          code,
          redirect_uri: `${window.location.origin}/auth/callback`,
          code_verifier: codeVerifier,
        }),
      })

      if (!response.ok) {
        throw new Error(`Token exchange failed: ${response.status}`)
      }

      const data = await response.json()
      _setTokens(data.access_token, data.refresh_token, data.expires_in)

      // Fetch seat/profile info from backend
      await fetchUserProfile()

      // Cache session in backend Redis (best-effort)
      try {
        const apiUrl = config.public.apiUrl as string
        await fetch(`${apiUrl}/api/v1/auth/session`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${data.access_token}`,
          },
          body: JSON.stringify({ user_agent: navigator.userAgent }),
        })
      }
      catch {
        // Best-effort — session cache is not critical
      }
    }
    catch (e) {
      error.value = e instanceof Error ? e.message : 'Authentication failed'
      console.error('Auth callback error:', e)
    }
    finally {
      isLoading.value = false
    }
  }

  /**
   * Store tokens and extract user info.
   */
  function _setTokens(
    access: string,
    refresh: string,
    expiresIn: number,
  ): void {
    accessToken.value = access
    refreshTokenValue.value = refresh

    const payload = parseJwtPayload(access)
    user.value = extractUser(payload)
    error.value = null

    // Schedule refresh before expiry (80% of lifetime)
    _scheduleRefresh(expiresIn)
  }

  /**
   * Schedule automatic token refresh.
   */
  function _scheduleRefresh(expiresIn: number): void {
    if (refreshTimer) clearTimeout(refreshTimer)
    const refreshAt = Math.max((expiresIn * 0.8) * 1000, 10000)
    refreshTimer = setTimeout(() => {
      refreshToken()
    }, refreshAt)
  }

  /**
   * Refresh the access token using the refresh token.
   */
  async function refreshToken(): Promise<boolean> {
    if (!refreshTokenValue.value) return false

    try {
      const response = await fetch(`${baseUrl}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          client_id: clientId,
          refresh_token: refreshTokenValue.value,
        }),
      })

      if (!response.ok) {
        _clearAuth()
        return false
      }

      const data = await response.json()
      _setTokens(data.access_token, data.refresh_token, data.expires_in)
      return true
    }
    catch {
      _clearAuth()
      return false
    }
  }

  /**
   * Get a valid access token, refreshing if needed.
   */
  async function getAccessToken(): Promise<string | null> {
    if (!accessToken.value) return null

    // Check if token is about to expire
    try {
      const payload = parseJwtPayload(accessToken.value)
      const exp = (payload.exp as number) ?? 0
      const now = Math.floor(Date.now() / 1000)

      if (exp - now < 30) {
        const success = await refreshToken()
        if (!success) return null
      }
    }
    catch {
      return null
    }

    return accessToken.value
  }

  /**
   * Logout — revoke token via backend, clear local state, redirect to login.
   * No Keycloak redirect, no confirmation prompt.
   */
  async function logout(): Promise<void> {
    const currentRefreshToken = refreshTokenValue.value

    // Clear local state immediately
    _clearAuth()

    if (import.meta.server) return

    // Best-effort: call backend to revoke token and clear Redis session
    if (currentRefreshToken) {
      try {
        const apiUrl = useRuntimeConfig().public.apiUrl as string
        await fetch(`${apiUrl}/api/v1/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: currentRefreshToken }),
        })
      }
      catch {
        // Best-effort — logout succeeds locally regardless
      }
    }

    // Clear any stored preferences/settings cache
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('horus-preferences-cache')
    }

    navigateTo('/login')
  }

  /**
   * Clear all auth state.
   */
  function _clearAuth(): void {
    accessToken.value = null
    refreshTokenValue.value = null
    user.value = null
    seats.value = []
    hasActiveSeat.value = false
    activeSeat.value = null
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
  }

  /**
   * Check if user has a specific role.
   */
  function hasRole(role: string): boolean {
    return user.value?.roles.includes(role) ?? false
  }

  /**
   * Check if user has any of the specified roles.
   */
  function hasAnyRole(...roles: string[]): boolean {
    return roles.some(role => hasRole(role))
  }

  /**
   * Fetch the user profile (with seat info) from the backend.
   * Called after login/callback to resolve seat-based access.
   */
  async function fetchUserProfile(): Promise<void> {
    if (!accessToken.value) return

    try {
      const apiUrl = config.public.apiUrl as string
      const response = await fetch(`${apiUrl}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken.value}` },
      })

      if (!response.ok) return

      const profile = await response.json()
      hasActiveSeat.value = profile.has_active_seat ?? false
      seats.value = (profile.seats ?? []).map((s: Record<string, unknown>) => ({
        id: s.id as string,
        organizationId: s.organization_id as string,
        organizationName: (s.organization_name as string) ?? null,
        role: s.role as string,
        isActive: s.is_active as boolean,
      }))
      activeSeat.value = seats.value.find(s => s.isActive) ?? null
    }
    catch {
      // Best-effort — seat info is not critical for auth flow
    }
  }

  // On first client load, resolve auth state quickly so the app can render
  if (import.meta.client && isLoading.value) {
    // No tokens stored → not authenticated, stop loading immediately
    isLoading.value = false
  }

  return {
    user,
    isAuthenticated,
    isLoading,
    accessToken,
    error,
    hasActiveSeat,
    activeSeat,
    seats,
    login,
    logout,
    handleCallback,
    refreshToken,
    getAccessToken,
    hasRole,
    hasAnyRole,
    fetchUserProfile,
  }
}
