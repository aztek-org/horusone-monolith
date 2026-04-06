/**
 * Global keyboard shortcuts composable.
 * Provides customizable key bindings with conflict detection, recording mode,
 * modifier support, and localStorage persistence.
 *
 * Module-level state is shared across all components that call useKeyboardShortcuts().
 * Actions are registered lazily — each page/component registers its own callbacks on mount.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ShortcutCategory = 'voice' | 'navigation' | 'general'

interface KeyModifiers {
  ctrl: boolean
  shift: boolean
  alt: boolean
}

interface KeyBinding {
  key: string // KeyboardEvent.code (e.g. "KeyB", "Space", "F1")
  modifiers: KeyModifiers
  label: string // Human-readable label
  description: string // What it does
  category: ShortcutCategory
  action: (() => void) | null // Callback — null until lazily registered
  enabled: boolean // Can be toggled on/off
}

interface ShortcutMap {
  [id: string]: KeyBinding
}

interface StoredBinding {
  key: string
  modifiers: KeyModifiers
  enabled: boolean
}

interface StoredBindings {
  [id: string]: StoredBinding
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'horus-keyboard-shortcuts'

const DEFAULT_BINDINGS: ShortcutMap = {
  push_to_talk: {
    key: 'KeyB',
    modifiers: { ctrl: false, shift: false, alt: false },
    label: 'Push to Talk',
    description: 'Press and hold to communicate with ATC',
    category: 'voice',
    action: null,
    enabled: true,
  },
  toggle_mic: {
    key: 'KeyM',
    modifiers: { ctrl: false, shift: false, alt: false },
    label: 'Toggle Microphone',
    description: 'Toggle microphone on/off',
    category: 'voice',
    action: null,
    enabled: true,
  },
  nav_dashboard: {
    key: 'KeyD',
    modifiers: { ctrl: true, shift: false, alt: false },
    label: 'Go to Dashboard',
    description: 'Navigate to the Dashboard page',
    category: 'navigation',
    action: null,
    enabled: true,
  },
  nav_library: {
    key: 'KeyL',
    modifiers: { ctrl: true, shift: false, alt: false },
    label: 'Go to Library',
    description: 'Navigate to the Scenario Library',
    category: 'navigation',
    action: null,
    enabled: true,
  },
  nav_configurator: {
    key: 'KeyK',
    modifiers: { ctrl: true, shift: false, alt: false },
    label: 'Go to Configurator',
    description: 'Navigate to the Scenario Configurator',
    category: 'navigation',
    action: null,
    enabled: true,
  },
  nav_settings: {
    key: 'Comma',
    modifiers: { ctrl: true, shift: false, alt: false },
    label: 'Go to Settings',
    description: 'Navigate to the Settings page',
    category: 'navigation',
    action: null,
    enabled: true,
  },
  toggle_shortcuts_help: {
    key: 'Slash',
    modifiers: { ctrl: true, shift: false, alt: false },
    label: 'Show Shortcuts Help',
    description: 'Open the keyboard shortcuts reference',
    category: 'general',
    action: null,
    enabled: true,
  },
  escape: {
    key: 'Escape',
    modifiers: { ctrl: false, shift: false, alt: false },
    label: 'Close / Cancel',
    description: 'Close modal or cancel current action',
    category: 'general',
    action: null,
    enabled: true,
  },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map KeyboardEvent.code → human-readable key label */
function getDisplayKey(code: string): string {
  const map: Record<string, string> = {
    Space: 'Space',
    Escape: 'Esc',
    Enter: 'Enter',
    Backspace: 'Backspace',
    Tab: 'Tab',
    Delete: 'Del',
    ArrowUp: '↑',
    ArrowDown: '↓',
    ArrowLeft: '←',
    ArrowRight: '→',
    Comma: ',',
    Period: '.',
    Slash: '/',
    Backslash: '\\',
    BracketLeft: '[',
    BracketRight: ']',
    Semicolon: ';',
    Quote: "'",
    Backquote: '`',
    Minus: '-',
    Equal: '=',
  }

  if (map[code]) return map[code]
  if (code.startsWith('Key')) return code.slice(3)
  if (code.startsWith('Digit')) return code.slice(5)
  if (code.startsWith('Numpad')) return `Num${code.slice(6)}`
  if (/^F\d+$/.test(code)) return code
  return code
}

/** Build a serialisation key for conflict detection: "ctrl+shift+KeyB" */
function buildComboKey(key: string, modifiers: KeyModifiers): string {
  const parts: string[] = []
  if (modifiers.ctrl) parts.push('ctrl')
  if (modifiers.shift) parts.push('shift')
  if (modifiers.alt) parts.push('alt')
  parts.push(key)
  return parts.join('+')
}

/** Build a display string like "Ctrl+Shift+B" */
function buildDisplayCombo(key: string, modifiers: KeyModifiers): string {
  const parts: string[] = []
  if (modifiers.ctrl) parts.push('Ctrl')
  if (modifiers.shift) parts.push('Shift')
  if (modifiers.alt) parts.push('Alt')
  parts.push(getDisplayKey(key))
  return parts.join('+')
}

/** Deep-clone modifiers so mutations don't leak */
function cloneModifiers(m: KeyModifiers): KeyModifiers {
  return { ctrl: m.ctrl, shift: m.shift, alt: m.alt }
}

/** Check whether the event target is an interactive text input */
function isEditableTarget(event: KeyboardEvent): boolean {
  const target = event.target as HTMLElement | null
  if (!target) return false
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (target.isContentEditable) return true
  return false
}

// ---------------------------------------------------------------------------
// Module-level state (singleton, shared across components)
// ---------------------------------------------------------------------------

const shortcuts = ref<ShortcutMap>(structuredClone(DEFAULT_BINDINGS))
const isRecording = ref(false)
const recordingId = ref<string | null>(null)

let listenerAttached = false
let listenerCount = 0

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

function loadFromStorage(): void {
  if (import.meta.server) return

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const stored: StoredBindings = JSON.parse(raw)

    for (const [id, saved] of Object.entries(stored)) {
      if (shortcuts.value[id]) {
        shortcuts.value[id].key = saved.key
        shortcuts.value[id].modifiers = cloneModifiers(saved.modifiers)
        shortcuts.value[id].enabled = saved.enabled
      }
    }
  }
  catch {
    // Corrupt data — ignore and keep defaults
    console.warn('[useKeyboardShortcuts] Failed to load saved shortcuts')
  }
}

function saveToStorage(): void {
  if (import.meta.server) return

  const stored: StoredBindings = {}
  for (const [id, binding] of Object.entries(shortcuts.value)) {
    stored[id] = {
      key: binding.key,
      modifiers: cloneModifiers(binding.modifiers),
      enabled: binding.enabled,
    }
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  }
  catch {
    console.warn('[useKeyboardShortcuts] Failed to persist shortcuts')
  }
}

// ---------------------------------------------------------------------------
// Global keyboard event handler
// ---------------------------------------------------------------------------

function handleKeyDown(event: KeyboardEvent): void {
  // Recording mode — capture the next key and apply it
  if (isRecording.value && recordingId.value) {
    event.preventDefault()
    event.stopPropagation()

    // Ignore bare modifier keys (user is still composing the combo)
    if (['Control', 'Shift', 'Alt', 'Meta'].includes(event.key)) return

    const newModifiers: KeyModifiers = {
      ctrl: event.ctrlKey || event.metaKey,
      shift: event.shiftKey,
      alt: event.altKey,
    }

    const targetId = recordingId.value

    // Conflict check (exclude the binding being recorded)
    const conflictId = findConflict(event.code, newModifiers, targetId)
    if (conflictId) {
      // Silently reject — caller can read hasConflict to show UI feedback
      stopRecording()
      return
    }

    shortcuts.value[targetId].key = event.code
    shortcuts.value[targetId].modifiers = newModifiers
    stopRecording()
    saveToStorage()
    return
  }

  // Don't fire shortcuts when the user is typing in a text field
  if (isEditableTarget(event)) return

  // Match against registered shortcuts
  for (const [_id, binding] of Object.entries(shortcuts.value)) {
    if (!binding.enabled || !binding.action) continue
    if (binding.key !== event.code) continue

    const wantCtrl = binding.modifiers.ctrl
    const wantShift = binding.modifiers.shift
    const wantAlt = binding.modifiers.alt

    const hasCtrl = event.ctrlKey || event.metaKey
    const hasShift = event.shiftKey
    const hasAlt = event.altKey

    if (wantCtrl !== hasCtrl) continue
    if (wantShift !== hasShift) continue
    if (wantAlt !== hasAlt) continue

    event.preventDefault()
    event.stopPropagation()
    binding.action()
    return
  }
}

function attachListener(): void {
  if (import.meta.server) return
  if (!listenerAttached) {
    window.addEventListener('keydown', handleKeyDown, { capture: true })
    listenerAttached = true
  }
  listenerCount++
}

function detachListener(): void {
  if (import.meta.server) return
  listenerCount--
  if (listenerCount <= 0) {
    window.removeEventListener('keydown', handleKeyDown, { capture: true })
    listenerAttached = false
    listenerCount = 0
  }
}

// ---------------------------------------------------------------------------
// Conflict detection
// ---------------------------------------------------------------------------

function findConflict(
  key: string,
  modifiers: KeyModifiers,
  excludeId?: string,
): string | null {
  const candidateCombo = buildComboKey(key, modifiers)

  for (const [id, binding] of Object.entries(shortcuts.value)) {
    if (excludeId && id === excludeId) continue
    const existingCombo = buildComboKey(binding.key, binding.modifiers)
    if (existingCombo === candidateCombo) return id
  }

  return null
}

// ---------------------------------------------------------------------------
// Load persisted bindings once at module init (client-only)
// ---------------------------------------------------------------------------

if (import.meta.client) {
  loadFromStorage()
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useKeyboardShortcuts() {
  // Attach the global listener when a component mounts, detach on unmount.
  // State itself survives unmount (module-level refs).
  onMounted(() => {
    attachListener()
  })

  onUnmounted(() => {
    detachListener()
  })

  // -- Public API -----------------------------------------------------------

  const readonlyShortcuts = computed<ShortcutMap>(() => shortcuts.value)

  /**
   * Register (or overwrite) the action callback for a shortcut id.
   * Pages call this on mount to wire up their own navigation / voice handlers.
   */
  function registerAction(id: string, action: () => void): void {
    if (!shortcuts.value[id]) {
      console.warn(`[useKeyboardShortcuts] Unknown shortcut id: "${id}"`)
      return
    }
    shortcuts.value[id].action = action
  }

  /**
   * Remove the action callback for a shortcut id (e.g. on page unmount).
   */
  function unregisterAction(id: string): void {
    if (shortcuts.value[id]) {
      shortcuts.value[id].action = null
    }
  }

  /**
   * Update the key binding for a given shortcut.
   * Returns `true` on success, `false` if the new combo conflicts.
   */
  function updateBinding(
    id: string,
    key: string,
    modifiers?: Partial<KeyModifiers>,
  ): boolean {
    if (!shortcuts.value[id]) return false

    const resolved: KeyModifiers = {
      ctrl: modifiers?.ctrl ?? false,
      shift: modifiers?.shift ?? false,
      alt: modifiers?.alt ?? false,
    }

    const conflict = findConflict(key, resolved, id)
    if (conflict) return false

    shortcuts.value[id].key = key
    shortcuts.value[id].modifiers = resolved
    saveToStorage()
    return true
  }

  /**
   * Reset all bindings to factory defaults.
   */
  function resetToDefaults(): void {
    const fresh = structuredClone(DEFAULT_BINDINGS)
    // Preserve any currently registered actions
    for (const [id, binding] of Object.entries(shortcuts.value)) {
      if (fresh[id] && binding.action) {
        fresh[id].action = binding.action
      }
    }
    shortcuts.value = fresh
    saveToStorage()
  }

  /**
   * Check if a key+modifier combo conflicts with an existing binding.
   * Returns the conflicting shortcut id, or null if no conflict.
   */
  function hasConflict(
    key: string,
    excludeId?: string,
    modifiers?: Partial<KeyModifiers>,
  ): string | null {
    const resolved: KeyModifiers = {
      ctrl: modifiers?.ctrl ?? false,
      shift: modifiers?.shift ?? false,
      alt: modifiers?.alt ?? false,
    }
    return findConflict(key, resolved, excludeId)
  }

  /**
   * Enter recording mode — the next non-modifier keypress updates the
   * binding for `id`.
   */
  function startRecording(id: string): void {
    if (!shortcuts.value[id]) return
    isRecording.value = true
    recordingId.value = id
  }

  /**
   * Exit recording mode without changing any binding.
   */
  function stopRecording(): void {
    isRecording.value = false
    recordingId.value = null
  }

  /**
   * Get the human-readable display string for a shortcut combo, e.g. "Ctrl+D".
   */
  function getDisplayCombo(id: string): string {
    const binding = shortcuts.value[id]
    if (!binding) return ''
    return buildDisplayCombo(binding.key, binding.modifiers)
  }

  return {
    shortcuts: readonlyShortcuts,
    isRecording,
    recordingId,
    registerAction,
    unregisterAction,
    updateBinding,
    resetToDefaults,
    hasConflict,
    startRecording,
    stopRecording,
    getDisplayKey,
    getDisplayCombo,
  }
}
