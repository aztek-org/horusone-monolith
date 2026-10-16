<template>
  <div class="fixed bottom-10 right-4 z-50">
    <!-- Main mic button -->
    <button
      :disabled="!status.connected || status.processing || status.pendingInstructor"
      :class="[
        'relative w-16 h-16 rounded-full shadow-lg transition-all duration-300',
        'flex items-center justify-center',
        'focus:outline-none focus:ring-2 focus:ring-offset-2',
        buttonClasses,
      ]"
      :title="buttonTitle"
      @mousedown="handleMouseDown"
      @mouseup="handleMouseUp"
      @touchstart="handleTouchStart"
      @touchend="handleTouchEnd"
    >
      <!-- Mic Icon -->
      <Icon
        v-if="!status.recording && !status.speaking"
        name="heroicons:microphone-solid"
        class="w-8 h-8"
      />

      <!-- Recording animation -->
      <div
        v-if="status.recording"
        class="w-8 h-8 animate-pulse"
      >
        <Icon
          name="heroicons:microphone-solid"
          class="w-8 h-8"
        />
      </div>

      <!-- Speaking indicator -->
      <div
        v-if="status.speaking"
        class="w-8 h-8"
      >
        <Icon
          name="heroicons:speaker-wave-solid"
          class="w-8 h-8 animate-pulse"
        />
      </div>

      <!-- Processing spinner -->
      <div
        v-if="status.processing"
        class="absolute inset-0 flex items-center justify-center"
      >
        <div class="w-12 h-12 border-2 border-t-transparent border-horus-accent-cyan rounded-full animate-spin" />
      </div>

      <!-- Pulse animation when recording -->
      <div
        v-if="status.recording"
        class="absolute inset-0 rounded-full bg-horus-status-danger opacity-50 animate-ping"
      />
    </button>

    <!-- Connection status indicator -->
    <div
      :class="[
        'absolute -top-1 -right-1 w-4 h-4 rounded-full border-2 border-horus-bg-primary',
        statusIndicatorClass,
      ]"
      :title="connectionStatusText"
    />

    <!-- Instructions tooltip -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-2"
    >
      <div
        v-if="showInstructions && !status.recording"
        class="absolute bottom-full right-0 mb-2 w-64 p-3 bg-horus-bg-elevated border border-horus-border-accent rounded-lg shadow-xl"
      >
        <p class="text-sm text-horus-text-secondary">
          <strong class="text-horus-text-primary">Push to talk:</strong><br>
          Press and hold to speak with ATC
        </p>
        <div class="mt-2 flex items-center gap-2 text-xs text-horus-text-muted">
          <kbd class="px-1.5 py-0.5 bg-horus-bg-tertiary border border-horus-border-subtle rounded text-horus-text-primary font-mono">{{ pushToTalkKey }}</kbd>
          <span>or click mic button</span>
        </div>
        <div class="mt-1 flex items-center gap-2 text-xs text-horus-text-muted">
          <div class="w-2 h-2 rounded-full bg-horus-status-success" />
          <span>Connected to tower</span>
        </div>
      </div>
    </Transition>

    <!-- Held-exchange notification (HITL) -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-2"
    >
      <div
        v-if="status.pendingInstructor"
        class="absolute bottom-full right-0 mb-2 w-64 p-3 bg-horus-status-warning/10 border border-horus-status-warning rounded-lg shadow-xl"
      >
        <p class="text-sm text-horus-status-warning font-medium">
          Transmission held for instructor review
        </p>
        <p class="mt-1 text-xs text-horus-text-muted">
          No ATC response will be sent until an instructor releases it.
        </p>
      </div>
    </Transition>

    <!-- Error notification -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-2"
    >
      <div
        v-if="status.error"
        class="absolute bottom-full right-0 mb-2 w-64 p-3 bg-horus-status-danger/10 border border-horus-status-danger rounded-lg shadow-xl"
      >
        <p class="text-sm text-horus-status-danger font-medium">
          {{ status.error }}
        </p>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useVoiceComm } from '~/composables/useVoiceComm'

// Use voice communication composable
const { status, connect, disconnect, startRecording, stopRecording } = useVoiceComm()
const { isAuthenticated } = useAuth()

// UI state
const showInstructions = ref(true)
const isKeyPressed = ref(false)
const pushToTalkKey = ref('B')

// Load settings from localStorage
function loadSettings() {
  const saved = localStorage.getItem('horus-settings')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (parsed.shortcuts?.pushToTalk) {
        pushToTalkKey.value = parsed.shortcuts.pushToTalk
      }
    }
    catch (e) {
      console.error('Failed to load settings:', e)
    }
  }
}

// Auto-connect when authenticated
watch(isAuthenticated, async (authed) => {
  if (authed) await connect()
  else disconnect()
})

// Auto-connect on mount if already authenticated
onMounted(async () => {
  if (isAuthenticated.value) await connect()

  // Load settings
  loadSettings()

  // Hide instructions after 5 seconds
  setTimeout(() => {
    showInstructions.value = false
  }, 5000)

  // Add keyboard event listeners
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)

  // Listen for storage changes to update settings in real-time
  window.addEventListener('storage', handleStorageChange)
})

// Clean up event listeners on unmount
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('storage', handleStorageChange)
})

function handleStorageChange(e: StorageEvent) {
  if (e.key === 'horus-settings') {
    loadSettings()
  }
}

// Computed classes
const buttonClasses = computed(() => {
  if (!status.value.connected) {
    return 'bg-horus-bg-tertiary text-horus-text-muted cursor-not-allowed'
  }

  if (status.value.recording) {
    return 'bg-horus-status-danger text-white scale-110 ring-2 ring-horus-status-danger ring-offset-2 ring-offset-horus-bg-primary'
  }

  if (status.value.processing) {
    return 'bg-horus-accent-cyan/20 text-horus-accent-cyan cursor-wait'
  }

  if (status.value.pendingInstructor) {
    return 'bg-horus-status-warning/20 text-horus-status-warning cursor-not-allowed'
  }

  if (status.value.speaking) {
    return 'bg-horus-status-info text-white animate-pulse-slow'
  }

  return 'bg-horus-accent-cyan text-horus-bg-primary hover:bg-horus-accent-cyan/90 hover:scale-105 active:scale-95 focus:ring-horus-accent-cyan'
})

const statusIndicatorClass = computed(() => {
  if (status.value.connected) {
    return 'bg-horus-status-success animate-pulse-slow'
  }
  return 'bg-horus-status-danger'
})

const connectionStatusText = computed(() => {
  return status.value.connected ? 'Connected to ATC' : 'Disconnected'
})

const buttonTitle = computed(() => {
  if (!status.value.connected) return 'Connecting to ATC...'
  if (status.value.pendingInstructor) return 'Transmission held for instructor review'
  if (status.value.recording) return 'Recording... Release to send'
  if (status.value.processing) return 'Processing transmission...'
  if (status.value.speaking) return 'ATC speaking...'
  return `Press and hold to talk to ATC (or press ${pushToTalkKey.value} key)`
})

// Event handlers
const handleMouseDown = () => {
  if (status.value.connected && !status.value.processing && !status.value.pendingInstructor) {
    startRecording()
  }
}

const handleMouseUp = () => {
  if (status.value.recording) {
    stopRecording()
  }
}

const handleTouchStart = (e: TouchEvent) => {
  e.preventDefault()
  handleMouseDown()
}

const handleTouchEnd = (e: TouchEvent) => {
  e.preventDefault()
  handleMouseUp()
}

// Keyboard event handlers for push-to-talk (dynamic key)
const handleKeyDown = (e: KeyboardEvent) => {
  // Build the pressed key combination
  let pressedKey = e.key.toUpperCase()
  if (e.ctrlKey && !pressedKey.includes('CONTROL')) pressedKey = `Ctrl+${pressedKey}`
  if (e.altKey && !pressedKey.includes('ALT')) pressedKey = `Alt+${pressedKey}`
  if (e.shiftKey && pressedKey.length > 1 && !pressedKey.includes('SHIFT')) pressedKey = `Shift+${pressedKey}`

  // Check if the configured key is pressed
  if (pressedKey === pushToTalkKey.value.toUpperCase() && !isKeyPressed.value) {
    // Prevent key repeat
    isKeyPressed.value = true

    // Don't trigger if user is typing in an input field
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return
    }

    // Start recording
    if (status.value.connected && !status.value.processing && !status.value.pendingInstructor) {
      e.preventDefault()
      startRecording()
    }
  }
}

const handleKeyUp = (e: KeyboardEvent) => {
  // Build the released key combination
  let releasedKey = e.key.toUpperCase()
  if (e.ctrlKey && !releasedKey.includes('CONTROL')) releasedKey = `Ctrl+${releasedKey}`
  if (e.altKey && !releasedKey.includes('ALT')) releasedKey = `Alt+${releasedKey}`
  if (e.shiftKey && releasedKey.length > 1 && !releasedKey.includes('SHIFT')) releasedKey = `Shift+${releasedKey}`

  // Check if the configured key is released
  if (releasedKey === pushToTalkKey.value.toUpperCase() && isKeyPressed.value) {
    isKeyPressed.value = false

    // Don't trigger if user is typing in an input field
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return
    }

    // Stop recording
    if (status.value.recording) {
      e.preventDefault()
      stopRecording()
    }
  }
}
</script>

<style scoped>
/* Custom animations are defined in main.css */
</style>
