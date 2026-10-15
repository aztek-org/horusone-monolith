import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockAuth = { authenticated: true }
const mockGet = vi.fn()
const mockPut = vi.fn()

vi.mock('./useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: {
      get value() {
        return mockAuth.authenticated
      },
    },
  }),
}))

vi.mock('./useApi', () => ({
  useApi: () => ({ get: mockGet, put: mockPut }),
}))

const CACHE_KEY = 'horus-preferences-cache'

function createMockLocalStorage() {
  const store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, val: string) => {
      store[key] = val
    }),
    removeItem: vi.fn((key: string) => {
      Reflect.deleteProperty(store, key)
    }),
    clear: vi.fn(() => {
      for (const k of Object.keys(store)) Reflect.deleteProperty(store, k)
    }),
    _store: store,
  }
}

let storage: ReturnType<typeof createMockLocalStorage>

async function setup(authenticated = true) {
  mockAuth.authenticated = authenticated
  vi.stubGlobal('localStorage', storage)
  const { usePreferences } = await import('./usePreferences')
  return usePreferences()
}

describe('usePreferences', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    mockAuth.authenticated = true
    mockGet.mockResolvedValue({ preferences: {} })
    mockPut.mockResolvedValue(undefined)
    storage = createMockLocalStorage()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  it('exposes the default preferences', async () => {
    const prefs = await setup()
    expect(prefs.preferences.value).toEqual({
      keyboard_shortcuts: { push_to_talk: 'KeyB' },
      voice: { radio_effects: true, language: 'en', ptt_mode: 'hold' },
      display: { animations: true, theme: 'dark', compact_mode: false },
    })
    expect(prefs.isLoading.value).toBe(false)
    expect(prefs.isSynced.value).toBe(false)
    expect(prefs.error.value).toBeNull()
  })

  it('loadFromCache deep-merges a partial cached object over the defaults', async () => {
    storage._store[CACHE_KEY] = JSON.stringify({
      display: { theme: 'light' },
      voice: { language: 'fr' },
    })
    const prefs = await setup()

    prefs.loadFromCache()

    expect(prefs.preferences.value.display).toEqual({
      animations: true,
      theme: 'light',
      compact_mode: false,
    })
    expect(prefs.preferences.value.voice).toEqual({
      radio_effects: true,
      language: 'fr',
      ptt_mode: 'hold',
    })
  })

  it('ignores a corrupted cache and keeps the defaults', async () => {
    storage._store[CACHE_KEY] = '{not json'
    const prefs = await setup()

    expect(() => prefs.loadFromCache()).not.toThrow()
    expect(prefs.preferences.value.display.theme).toBe('dark')
  })

  it('initialize loads the cache and then merges the backend response', async () => {
    storage._store[CACHE_KEY] = JSON.stringify({ voice: { language: 'de' } })
    mockGet.mockResolvedValue({
      preferences: { display: { compact_mode: true } },
    })
    const prefs = await setup()

    await prefs.initialize()

    expect(mockGet).toHaveBeenCalledWith('/api/v1/users/me/preferences/')
    expect(prefs.preferences.value.display.compact_mode).toBe(true)
    // NOTE: fetchFromBackend deep-merges the response over DEFAULTS (not over the
    // cache-loaded value), so the cached `voice.language` is replaced by 'en'.
    expect(prefs.preferences.value.voice.language).toBe('en')
    expect(prefs.isSynced.value).toBe(true)
    // Backend merge is persisted back to cache
    expect(storage.setItem).toHaveBeenCalledWith(CACHE_KEY, expect.any(String))
  })

  it('skips the backend fetch when unauthenticated', async () => {
    const prefs = await setup(false)
    await prefs.initialize()
    expect(mockGet).not.toHaveBeenCalled()
    expect(prefs.isSynced.value).toBe(false)
  })

  it('sets an error and clears loading when the backend fetch fails', async () => {
    mockGet.mockRejectedValue(new Error('offline'))
    const prefs = await setup()

    await prefs.initialize()

    expect(prefs.error.value).toBe('Failed to load preferences from server')
    expect(prefs.isLoading.value).toBe(false)
    expect(prefs.isSynced.value).toBe(false)
  })

  it('saveToBackend persists to cache and backend when authenticated', async () => {
    const prefs = await setup()
    const ok = await prefs.saveToBackend()

    expect(ok).toBe(true)
    expect(storage.setItem).toHaveBeenCalledWith(CACHE_KEY, expect.any(String))
    expect(mockPut).toHaveBeenCalledWith('/api/v1/users/me/preferences/', {
      preferences: prefs.preferences.value,
    })
    expect(prefs.isSynced.value).toBe(true)
  })

  it('saveToBackend still caches but skips the network when unauthenticated', async () => {
    const prefs = await setup(false)
    const ok = await prefs.saveToBackend()

    expect(ok).toBe(false)
    expect(storage.setItem).toHaveBeenCalled()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('saveToBackend reports failure from the backend', async () => {
    mockPut.mockRejectedValue(new Error('server error'))
    const prefs = await setup()
    const ok = await prefs.saveToBackend()
    expect(ok).toBe(false)
    expect(prefs.error.value).toBe('Failed to save preferences to server')
  })

  it('updateSection replaces a section and persists changes', async () => {
    const prefs = await setup()
    await prefs.updateSection('display', {
      animations: false,
      theme: 'light',
      compact_mode: true,
    })

    expect(prefs.preferences.value.display).toEqual({
      animations: false,
      theme: 'light',
      compact_mode: true,
    })
    expect(mockPut).toHaveBeenCalled()
  })

  it('resetToDefaults restores the defaults and syncs them', async () => {
    const prefs = await setup()
    await prefs.updateSection('display', { animations: false, theme: 'light', compact_mode: true })

    await prefs.resetToDefaults()

    expect(prefs.preferences.value.display).toEqual({
      animations: true,
      theme: 'dark',
      compact_mode: false,
    })
    expect(storage.setItem).toHaveBeenCalled()
  })
})
