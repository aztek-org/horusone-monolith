<template>
  <div class="min-h-screen bg-horus-bg-primary">
    <!-- Header -->
    <header class="sticky top-0 z-40 bg-horus-bg-primary/95 backdrop-blur-md border-b border-horus-border-subtle">
      <div class="flex items-center justify-between h-14 px-4 lg:px-6">
        <div class="flex items-center gap-4">
          <NuxtLink
            to="/"
            class="p-2 -ml-2 text-horus-text-secondary hover:text-horus-text-primary transition-colors"
          >
            <Icon name="heroicons:arrow-left" class="w-5 h-5" />
          </NuxtLink>
          <div>
            <h1 class="text-sm font-semibold text-horus-text-primary">Settings</h1>
            <p class="text-xxs text-horus-text-muted tracking-wider">CONFIGURE YOUR EXPERIENCE</p>
          </div>
        </div>
      </div>
    </header>

    <!-- Content -->
    <div class="max-w-5xl mx-auto px-4 lg:px-6 py-8">
      <div class="space-y-6">
        <!-- Keyboard Shortcuts Section -->
        <HCard>
          <template #header>
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
                <Icon name="heroicons:command-line" class="w-6 h-6 text-horus-accent-cyan" />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-horus-text-primary">Keyboard Shortcuts</h2>
                <p class="text-sm text-horus-text-secondary">Customize hotkeys for quick actions</p>
              </div>
            </div>
          </template>

          <div class="space-y-4">
            <!-- Push to Talk -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle hover:border-horus-border-accent transition-colors">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-medium text-horus-text-primary">Push to Talk</h3>
                  <HBadge variant="cyan" size="sm">Voice</HBadge>
                </div>
                <p class="text-xs text-horus-text-secondary mt-1">Press and hold to communicate with ATC</p>
              </div>
              <div class="flex items-center gap-3">
                <button
                  class="px-4 py-2 bg-horus-bg-tertiary border border-horus-border-subtle rounded-lg hover:border-horus-accent-cyan transition-colors group"
                  @click="editingShortcut = 'pushToTalk'"
                >
                  <div class="flex items-center gap-2">
                    <kbd class="px-2 py-1 bg-horus-bg-primary border border-horus-border-subtle rounded text-horus-text-primary font-mono text-sm group-hover:border-horus-accent-cyan group-hover:text-horus-accent-cyan transition-colors">
                      {{ shortcuts.pushToTalk }}
                    </kbd>
                    <Icon name="heroicons:pencil" class="w-4 h-4 text-horus-text-muted group-hover:text-horus-accent-cyan transition-colors" />
                  </div>
                </button>
                <button
                  v-if="shortcuts.pushToTalk !== 'B'"
                  @click="resetShortcut('pushToTalk')"
                  class="text-sm text-horus-text-muted hover:text-horus-accent-cyan transition-colors"
                  title="Reset to default"
                >
                  <Icon name="heroicons:arrow-path" class="w-5 h-5" />
                </button>
              </div>
            </div>

            <!-- Future shortcuts -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary/50 border border-horus-border-subtle opacity-50">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-medium text-horus-text-primary">Toggle Map View</h3>
                  <HBadge variant="default" size="sm">Navigation</HBadge>
                </div>
                <p class="text-xs text-horus-text-secondary mt-1">Switch between map and list view</p>
              </div>
              <div class="flex items-center gap-3">
                <kbd class="px-2 py-1 bg-horus-bg-tertiary border border-horus-border-subtle rounded text-horus-text-muted font-mono text-sm">
                  M
                </kbd>
                <span class="text-xs text-horus-text-muted">Coming Soon</span>
              </div>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary/50 border border-horus-border-subtle opacity-50">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-medium text-horus-text-primary">Quick Save Scenario</h3>
                  <HBadge variant="default" size="sm">Scenario</HBadge>
                </div>
                <p class="text-xs text-horus-text-secondary mt-1">Save current scenario quickly</p>
              </div>
              <div class="flex items-center gap-3">
                <kbd class="px-2 py-1 bg-horus-bg-tertiary border border-horus-border-subtle rounded text-horus-text-muted font-mono text-sm">
                  Ctrl+S
                </kbd>
                <span class="text-xs text-horus-text-muted">Coming Soon</span>
              </div>
            </div>
          </div>
        </HCard>

        <!-- Voice Communication Settings -->
        <HCard>
          <template #header>
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-status-info/20 flex items-center justify-center">
                <Icon name="heroicons:microphone" class="w-6 h-6 text-horus-status-info" />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-horus-text-primary">Voice Communication</h2>
                <p class="text-sm text-horus-text-secondary">Configure ATC voice settings</p>
              </div>
            </div>
          </template>

          <div class="space-y-4">
            <!-- Radio Effects -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Radio Effects</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Apply authentic radio static and filters</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="voiceSettings.radioEffects" class="sr-only peer">
                <div class="w-11 h-6 bg-horus-bg-tertiary peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-horus-accent-cyan"></div>
              </label>
            </div>

            <!-- Language Preference -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Preferred Language</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Default language for ATC communication</p>
              </div>
              <div class="w-48">
                <HDropdown
                  v-model="voiceSettings.language"
                  :options="languageOptions"
                  placeholder="Select language"
                />
              </div>
            </div>

            <!-- Push to Talk Behavior -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Push-to-Talk Mode</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Hold button/key to record, release to send</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="voiceSettings.pushToTalkMode" checked disabled class="sr-only peer">
                <div class="w-11 h-6 bg-horus-accent-cyan peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all opacity-50 cursor-not-allowed"></div>
              </label>
            </div>
          </div>
        </HCard>

        <!-- Display Settings -->
        <HCard>
          <template #header>
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-status-warning/20 flex items-center justify-center">
                <Icon name="heroicons:computer-desktop" class="w-6 h-6 text-horus-status-warning" />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-horus-text-primary">Display Settings</h2>
                <p class="text-sm text-horus-text-secondary">Customize visual preferences</p>
              </div>
            </div>
          </template>

          <div class="space-y-4">
            <!-- Theme mode (coming soon) -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary/50 border border-horus-border-subtle opacity-50">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Theme Mode</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Switch between dark and light themes</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-sm text-horus-text-muted">Dark Mode</span>
                <span class="text-xs text-horus-text-muted">Coming Soon</span>
              </div>
            </div>

            <!-- Animations -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Animations</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Enable or disable UI animations</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="displaySettings.animations" class="sr-only peer">
                <div class="w-11 h-6 bg-horus-bg-tertiary peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-horus-accent-cyan"></div>
              </label>
            </div>
          </div>
        </HCard>

        <!-- Actions -->
        <div class="flex items-center justify-between gap-4 pt-4">
          <HButton
            variant="secondary"
            @click="resetAllSettings"
          >
            <Icon name="heroicons:arrow-path" class="w-4 h-4" />
            Reset All to Defaults
          </HButton>
          <div class="flex items-center gap-3">
            <NuxtLink to="/">
              <HButton variant="secondary">
                Cancel
              </HButton>
            </NuxtLink>
            <HButton
              variant="primary"
              @click="saveSettings"
            >
              <Icon name="heroicons:check" class="w-4 h-4" />
              Save Changes
            </HButton>
          </div>
        </div>
      </div>
    </div>

    <!-- Shortcut Edit Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="editingShortcut"
          class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          @click.self="cancelEditShortcut"
        >
          <div class="bg-horus-bg-elevated border border-horus-border-accent rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 class="text-lg font-semibold text-horus-text-primary mb-2">Press a Key</h3>
            <p class="text-sm text-horus-text-secondary mb-6">Press any key to set as the new shortcut for Push to Talk</p>
            
            <div class="flex items-center justify-center p-8 bg-horus-bg-secondary border-2 border-dashed border-horus-border-accent rounded-lg mb-6">
              <div class="text-center">
                <Icon name="heroicons:command-line" class="w-12 h-12 text-horus-accent-cyan mx-auto mb-2 animate-pulse" />
                <p class="text-sm text-horus-text-muted">Waiting for key press...</p>
              </div>
            </div>

            <div class="flex gap-3">
              <HButton
                variant="secondary"
                class="flex-1"
                @click="cancelEditShortcut"
              >
                Cancel
              </HButton>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

// Settings state
const shortcuts = ref({
  pushToTalk: 'B',
})

const voiceSettings = ref({
  radioEffects: true,
  language: 'auto',
  pushToTalkMode: true,
})

const displaySettings = ref({
  animations: true,
})

const editingShortcut = ref<string | null>(null)

// Language options for dropdown
const languageOptions = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish (Español)' },
]

const languageLabel = computed(() => {
  switch (voiceSettings.value.language) {
    case 'auto': return 'Auto-detect'
    case 'en': return 'English'
    case 'es': return 'Spanish (Español)'
    default: return 'Auto-detect'
  }
})

// Load settings from localStorage
onMounted(() => {
  const saved = localStorage.getItem('horus-settings')
  if (saved) {
    const parsed = JSON.parse(saved)
    if (parsed.shortcuts) shortcuts.value = { ...shortcuts.value, ...parsed.shortcuts }
    if (parsed.voiceSettings) voiceSettings.value = { ...voiceSettings.value, ...parsed.voiceSettings }
    if (parsed.displaySettings) displaySettings.value = { ...displaySettings.value, ...parsed.displaySettings }
  }

  // Add keyboard listener for shortcut editing
  window.addEventListener('keydown', handleShortcutKeyPress)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleShortcutKeyPress)
})

function handleShortcutKeyPress(e: KeyboardEvent) {
  if (editingShortcut.value) {
    e.preventDefault()
    
    // Get the key name
    let keyName = e.key.toUpperCase()
    
    // Handle special keys
    if (e.ctrlKey) keyName = `Ctrl+${keyName}`
    if (e.altKey) keyName = `Alt+${keyName}`
    if (e.shiftKey && keyName.length > 1) keyName = `Shift+${keyName}`
    
    // Update the shortcut
    if (editingShortcut.value === 'pushToTalk') {
      shortcuts.value.pushToTalk = keyName
    }
    
    editingShortcut.value = null
  }
}

function resetShortcut(shortcut: string) {
  if (shortcut === 'pushToTalk') {
    shortcuts.value.pushToTalk = 'B'
  }
}

function cancelEditShortcut() {
  editingShortcut.value = null
}

function saveSettings() {
  const settings = {
    shortcuts: shortcuts.value,
    voiceSettings: voiceSettings.value,
    displaySettings: displaySettings.value,
  }
  localStorage.setItem('horus-settings', JSON.stringify(settings))
  
  // Show success feedback (you could add a toast notification here)
  console.log('Settings saved successfully')
  
  // Navigate back
  navigateTo('/')
}

function resetAllSettings() {
  shortcuts.value = { pushToTalk: 'B' }
  voiceSettings.value = {
    radioEffects: true,
    language: 'auto',
    pushToTalkMode: true,
  }
  displaySettings.value = {
    animations: true,
  }
}
</script>
