import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helper: mount a tiny wrapper component that calls the composable so
// onMounted / onUnmounted hooks fire in a real component lifecycle.
// ---------------------------------------------------------------------------

async function mountWithComposable(mockStorage?: ReturnType<typeof createMockLocalStorage>) {
  if (mockStorage) {
    vi.stubGlobal('localStorage', mockStorage)
  }

  const mod = await import('./useKeyboardShortcuts')
  let api: ReturnType<typeof mod.useKeyboardShortcuts>

  const Wrapper = defineComponent({
    setup() {
      api = mod.useKeyboardShortcuts()
      return {}
    },
    template: '<div />',
  })

  const wrapper = mount(Wrapper)
  // api is assigned synchronously inside setup()
  return { wrapper, api: api!, mod }
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe('useKeyboardShortcuts', () => {
  let mockLocalStorage: ReturnType<typeof createMockLocalStorage>

  beforeEach(() => {
    vi.resetModules()
    mockLocalStorage = createMockLocalStorage()
    vi.stubGlobal('localStorage', mockLocalStorage)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // Convenience for tests that don't need lifecycle
  async function loadComposable() {
    const { api } = await mountWithComposable(mockLocalStorage)
    return api
  }

  // -- Initialisation -------------------------------------------------------

  it('returns default shortcuts on first load', async () => {
    const { shortcuts } = await loadComposable()
    const map = shortcuts.value

    expect(map.push_to_talk).toBeDefined()
    expect(map.push_to_talk.key).toBe('KeyB')
    expect(map.push_to_talk.category).toBe('voice')

    expect(map.nav_dashboard).toBeDefined()
    expect(map.nav_dashboard.modifiers.ctrl).toBe(true)
    expect(map.nav_dashboard.key).toBe('KeyD')

    expect(map.escape).toBeDefined()
    expect(map.escape.key).toBe('Escape')
  })

  it('initialises isRecording to false and recordingId to null', async () => {
    const { isRecording, recordingId } = await loadComposable()
    expect(isRecording.value).toBe(false)
    expect(recordingId.value).toBeNull()
  })

  it('attaches a keydown listener on mount and removes it on unmount', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')

    const { wrapper } = await mountWithComposable(mockLocalStorage)

    expect(addSpy).toHaveBeenCalledWith(
      'keydown',
      expect.any(Function),
      expect.objectContaining({ capture: true }),
    )

    wrapper.unmount()

    expect(removeSpy).toHaveBeenCalledWith(
      'keydown',
      expect.any(Function),
      expect.objectContaining({ capture: true }),
    )
  })

  // -- getDisplayKey / getDisplayCombo --------------------------------------

  it('getDisplayKey converts KeyboardEvent.code to readable labels', async () => {
    const { getDisplayKey } = await loadComposable()

    expect(getDisplayKey('KeyB')).toBe('B')
    expect(getDisplayKey('Space')).toBe('Space')
    expect(getDisplayKey('Comma')).toBe(',')
    expect(getDisplayKey('Slash')).toBe('/')
    expect(getDisplayKey('Digit5')).toBe('5')
    expect(getDisplayKey('F1')).toBe('F1')
    expect(getDisplayKey('Escape')).toBe('Esc')
  })

  it('getDisplayCombo formats modifier+key as "Ctrl+D" style string', async () => {
    const { getDisplayCombo } = await loadComposable()

    expect(getDisplayCombo('nav_dashboard')).toBe('Ctrl+D')
    expect(getDisplayCombo('push_to_talk')).toBe('B')
    expect(getDisplayCombo('nav_settings')).toBe('Ctrl+,')
    expect(getDisplayCombo('toggle_shortcuts_help')).toBe('Ctrl+/')
  })

  it('getDisplayCombo returns empty string for unknown id', async () => {
    const { getDisplayCombo } = await loadComposable()
    expect(getDisplayCombo('nonexistent')).toBe('')
  })

  // -- registerAction / unregisterAction ------------------------------------

  it('registerAction wires up a callback; unregisterAction clears it', async () => {
    const { shortcuts, registerAction, unregisterAction } = await loadComposable()

    expect(shortcuts.value.push_to_talk.action).toBeNull()

    const spy = vi.fn()
    registerAction('push_to_talk', spy)
    expect(shortcuts.value.push_to_talk.action).toBe(spy)

    unregisterAction('push_to_talk')
    expect(shortcuts.value.push_to_talk.action).toBeNull()
  })

  it('registerAction warns for unknown shortcut id', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { registerAction } = await loadComposable()

    registerAction('unknown_shortcut', vi.fn())
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Unknown shortcut id'),
    )
  })

  // -- updateBinding --------------------------------------------------------

  it('updateBinding changes the key and persists to localStorage', async () => {
    const { shortcuts, updateBinding } = await loadComposable()

    const ok = updateBinding('push_to_talk', 'KeyT')
    expect(ok).toBe(true)
    expect(shortcuts.value.push_to_talk.key).toBe('KeyT')

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      'horus-keyboard-shortcuts',
      expect.any(String),
    )
  })

  it('updateBinding rejects when the combo conflicts with another shortcut', async () => {
    const { shortcuts, updateBinding } = await loadComposable()

    // Try to set push_to_talk to "KeyM" which conflicts with toggle_mic
    const ok = updateBinding('push_to_talk', 'KeyM')
    expect(ok).toBe(false)
    // Original binding unchanged
    expect(shortcuts.value.push_to_talk.key).toBe('KeyB')
  })

  it('updateBinding returns false for unknown shortcut id', async () => {
    const { updateBinding } = await loadComposable()
    expect(updateBinding('no_such_id', 'KeyX')).toBe(false)
  })

  it('updateBinding accepts modifiers and saves them', async () => {
    const { shortcuts, updateBinding } = await loadComposable()

    const ok = updateBinding('push_to_talk', 'KeyT', { ctrl: true, shift: true })
    expect(ok).toBe(true)
    expect(shortcuts.value.push_to_talk.key).toBe('KeyT')
    expect(shortcuts.value.push_to_talk.modifiers.ctrl).toBe(true)
    expect(shortcuts.value.push_to_talk.modifiers.shift).toBe(true)
    expect(shortcuts.value.push_to_talk.modifiers.alt).toBe(false)
  })

  // -- hasConflict ----------------------------------------------------------

  it('hasConflict returns the conflicting id when a combo is taken', async () => {
    const { hasConflict } = await loadComposable()

    // KeyB without modifiers is taken by push_to_talk
    expect(hasConflict('KeyB')).toBe('push_to_talk')
  })

  it('hasConflict returns null when the combo is free', async () => {
    const { hasConflict } = await loadComposable()
    expect(hasConflict('KeyZ')).toBeNull()
  })

  it('hasConflict excludes the specified id from the check', async () => {
    const { hasConflict } = await loadComposable()
    // KeyB is push_to_talk, but excluding push_to_talk should yield no conflict
    expect(hasConflict('KeyB', 'push_to_talk')).toBeNull()
  })

  it('hasConflict differentiates by modifiers', async () => {
    const { hasConflict } = await loadComposable()

    // KeyD with Ctrl is nav_dashboard
    expect(hasConflict('KeyD', undefined, { ctrl: true })).toBe('nav_dashboard')
    // KeyD without Ctrl is free
    expect(hasConflict('KeyD')).toBeNull()
  })

  // -- resetToDefaults ------------------------------------------------------

  it('resetToDefaults restores factory bindings but keeps registered actions', async () => {
    const { shortcuts, updateBinding, resetToDefaults, registerAction }
      = await loadComposable()

    const action = vi.fn()
    registerAction('push_to_talk', action)
    updateBinding('push_to_talk', 'KeyT')
    expect(shortcuts.value.push_to_talk.key).toBe('KeyT')

    resetToDefaults()

    expect(shortcuts.value.push_to_talk.key).toBe('KeyB')
    expect(shortcuts.value.push_to_talk.action).toBe(action)
  })

  it('resetToDefaults persists the reset to localStorage', async () => {
    const { updateBinding, resetToDefaults } = await loadComposable()
    updateBinding('push_to_talk', 'KeyT')
    mockLocalStorage.setItem.mockClear()

    resetToDefaults()

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      'horus-keyboard-shortcuts',
      expect.any(String),
    )
  })

  // -- Recording mode -------------------------------------------------------

  it('startRecording / stopRecording toggle recording state', async () => {
    const { isRecording, recordingId, startRecording, stopRecording }
      = await loadComposable()

    startRecording('push_to_talk')
    expect(isRecording.value).toBe(true)
    expect(recordingId.value).toBe('push_to_talk')

    stopRecording()
    expect(isRecording.value).toBe(false)
    expect(recordingId.value).toBeNull()
  })

  it('startRecording is a no-op for unknown id', async () => {
    const { isRecording, startRecording } = await loadComposable()

    startRecording('nonexistent')
    expect(isRecording.value).toBe(false)
  })

  // -- Persistence ----------------------------------------------------------

  it('loads saved bindings from localStorage on init', async () => {
    // Pre-populate storage BEFORE importing the module
    const stored = {
      push_to_talk: {
        key: 'KeyT',
        modifiers: { ctrl: false, shift: false, alt: false },
        enabled: true,
      },
    }
    mockLocalStorage._store['horus-keyboard-shortcuts'] = JSON.stringify(stored)

    const { shortcuts } = await loadComposable()
    expect(shortcuts.value.push_to_talk.key).toBe('KeyT')
  })

  it('handles corrupt localStorage data gracefully', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mockLocalStorage._store['horus-keyboard-shortcuts'] = '{invalid json'

    // Should not throw
    const { shortcuts } = await loadComposable()
    // Falls back to defaults
    expect(shortcuts.value.push_to_talk.key).toBe('KeyB')
    expect(warnSpy).toHaveBeenCalled()
  })

  // -- Category coverage ----------------------------------------------------

  it('all default shortcuts have valid categories', async () => {
    const { shortcuts } = await loadComposable()
    const validCategories = new Set(['voice', 'navigation', 'general'])

    for (const binding of Object.values(shortcuts.value)) {
      expect(validCategories.has(binding.category)).toBe(true)
    }
  })

  it('provides the expected set of default shortcut ids', async () => {
    const { shortcuts } = await loadComposable()
    const ids = Object.keys(shortcuts.value).sort()

    expect(ids).toEqual([
      'escape',
      'nav_configurator',
      'nav_dashboard',
      'nav_library',
      'nav_settings',
      'push_to_talk',
      'toggle_mic',
      'toggle_shortcuts_help',
    ])
  })
})
