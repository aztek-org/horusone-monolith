/**
 * Typed API client composable for backend communication.
 * Automatically injects JWT auth headers and handles errors.
 */

interface ApiOptions {
  /** Skip authentication header */
  noAuth?: boolean
}

interface ApiError {
  status: number
  detail: string
}

export function useApi() {
  const config = useRuntimeConfig()
  const baseUrl = config.public.apiUrl as string
  const { getAccessToken, isAuthenticated } = useAuth()

  /**
   * Make an authenticated API request.
   */
  async function request<T>(
    path: string,
    options: RequestInit & ApiOptions = {},
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (!options.noAuth && isAuthenticated.value) {
      const token = await getAccessToken()
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
    }

    const response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers,
    })

    if (!response.ok) {
      let detail = `Request failed: ${response.status}`
      try {
        const body = await response.json()
        detail = body.detail || detail
      }
      catch { /* ignore parse errors */ }

      const apiError: ApiError = { status: response.status, detail }
      throw apiError
    }

    if (response.status === 204) return undefined as T

    return response.json()
  }

  function get<T>(path: string, opts?: ApiOptions): Promise<T> {
    return request<T>(path, { method: 'GET', ...opts })
  }

  function post<T>(path: string, body?: unknown, opts?: ApiOptions): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      ...opts,
    })
  }

  function put<T>(path: string, body?: unknown, opts?: ApiOptions): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
      ...opts,
    })
  }

  function del<T>(path: string, opts?: ApiOptions): Promise<T> {
    return request<T>(path, { method: 'DELETE', ...opts })
  }

  /**
   * Get WebSocket URL with auth token as query param.
   */
  async function getAuthenticatedWsUrl(path?: string): Promise<string> {
    const wsBase = config.public.wsUrl as string
    const wsUrl = path ? `${wsBase.replace(/\/ws\/voice$/, '')}${path}` : wsBase
    const token = await getAccessToken()
    return token ? `${wsUrl}?token=${token}` : wsUrl
  }

  return {
    get,
    post,
    put,
    del,
    request,
    getAuthenticatedWsUrl,
  }
}
