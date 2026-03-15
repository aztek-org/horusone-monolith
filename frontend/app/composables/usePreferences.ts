/**
 * User preferences composable with backend sync and local cache.
 * Reads from localStorage cache first, syncs with backend API in background.
 */

export interface VoicePreferences {
  radio_effects: boolean
  language: string
  ptt_mode: string
}

export interface DisplayPreferences {
  animations: boolean
  theme: string
  compact_mode: boolean
}

export interface PreferencesData {
  keyboard_shortcuts: Record<string, string>
  voice: VoicePreferences
  display: DisplayPreferences
}

const CACHE_KEY = 'horus-preferences-cache'
const DEFAULTS: PreferencesData = {
  keyboard_shortcuts: { push_to_talk: 'KeyB' },
  voice: { radio_effects: true, language: 'en', ptt_mode: 'hold' },
  display: { animations: true, theme: 'dark', compact_mode: false },
}

// Module-level state (shared across components)
const preferences = ref<PreferencesData>({ ...DEFAULTS })
const isLoading = ref(false)
const isSynced = ref(false)
const error = ref<string | null>(null)

/**
 * Deep merge source into target (non-destructive).
 */
function deepMerge(target: Record<string, unknown>, source: Record<string, unknown>): Record<string, unknown> {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    if (
      source[key] !== null &&
      typeof source[key] === 'object' &&
      !Array.isArray(source[key]) &&
      typeof result[key] === 'object' &&
      result[key] !== null &&
      !Array.isArray(result[key])
    ) {
      result[key] = deepMerge(result[key] as Record<string, unknown>, source[key] as Record<string, unknown>)
    } else {
      result[key] = source[key]
    }
  }
  return result
}

export function usePreferences() {
  const { isAuthenticated } = useAuth()

  /**
   * Load preferences from local cache.
   */
  function loadFromCache(): void {
    if (import.meta.server) return
    try {
      const cached = localStorage.getItem(CACHE_KEY)
      if (cached) {
        const parsed = JSON.parse(cached) as Partial<PreferencesData>
        preferences.value = deepMerge(DEFAULTS, parsed as Record<string, unknown>) as PreferencesData
      }
    } catch {
      // Corrupted cache — use defaults
    }
  }

  /**
   * Save preferences to local cache.
   */
  function saveToCache(): void {
    if (import.meta.server) return
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(preferences.value))
    } catch {
      // localStorage full or disabled — ignore
    }
  }

  /**
   * Fetch preferences from backend and merge with local state.
   */
  async function fetchFromBackend(): Promise<void> {
    if (!isAuthenticated.value) return

    try {
      isLoading.value = true
      error.value = null

      const { get } = useApi()
      const response = await get<{ preferences: PreferencesData }>('/api/v1/users/me/preferences/')
      if (response?.preferences) {
        preferences.value = deepMerge(DEFAULTS, response.preferences as Record<string, unknown>) as PreferencesData
        saveToCache()
        isSynced.value = true
      }
    } catch (e) {
      error.value = 'Failed to load preferences from server'
      console.warn('Preferences fetch failed, using local cache:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Save preferences to backend and update local cache.
   */
  async function saveToBackend(): Promise<boolean> {
    saveToCache()

    if (!isAuthenticated.value) return false

    try {
      isLoading.value = true
      error.value = null

      const { put } = useApi()
      await put('/api/v1/users/me/preferences/', { preferences: preferences.value })
      isSynced.value = true
      return true
    } catch (e) {
      error.value = 'Failed to save preferences to server'
      console.warn('Preferences save failed:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update a specific section of preferences.
   */
  async function updateSection(section: keyof PreferencesData, data: unknown): Promise<boolean> {
    preferences.value = {
      ...preferences.value,
      [section]: data,
    }
    return saveToBackend()
  }

  /**
   * Reset all preferences to defaults.
   */
  async function resetToDefaults(): Promise<void> {
    preferences.value = { ...DEFAULTS }
    saveToCache()
    if (isAuthenticated.value) {
      await saveToBackend()
    }
  }

  /**
   * Initialize: load from cache immediately, then sync from backend.
   */
  async function initialize(): Promise<void> {
    loadFromCache()
    await fetchFromBackend()
  }

  return {
    preferences,
    isLoading: computed(() => isLoading.value),
    isSynced: computed(() => isSynced.value),
    error: computed(() => error.value),
    initialize,
    saveToBackend,
    updateSection,
    resetToDefaults,
    loadFromCache,
  }
}
