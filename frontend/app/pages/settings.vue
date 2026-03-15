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
        <div class="flex items-center gap-2">
          <span v-if="prefSynced" class="text-xs text-horus-status-success flex items-center gap-1">
            <Icon name="heroicons:check-circle" class="w-4 h-4" />
            Synced
          </span>
          <span v-else-if="prefError" class="text-xs text-horus-status-warning flex items-center gap-1">
            <Icon name="heroicons:exclamation-triangle" class="w-4 h-4" />
            Local only
          </span>
        </div>
      </div>
    </header>

    <!-- Content -->
    <div class="max-w-5xl mx-auto px-4 lg:px-6 py-8">
      <div class="space-y-6">
        <!-- Keyboard Shortcuts Section -->
        <HCard>
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
                  <Icon name="heroicons:command-line" class="w-6 h-6 text-horus-accent-cyan" />
                </div>
                <div>
                  <h2 class="text-lg font-semibold text-horus-text-primary">Keyboard Shortcuts</h2>
                  <p class="text-sm text-horus-text-secondary">Customize hotkeys for quick actions</p>
                </div>
              </div>
              <button
                class="text-xs text-horus-text-muted hover:text-horus-accent-cyan transition-colors flex items-center gap-1"
                @click="showShortcutsHelp = true"
              >
                <Icon name="heroicons:question-mark-circle" class="w-4 h-4" />
                View All (Ctrl+/)
              </button>
            </div>
          </template>

          <div class="space-y-3">
            <div
              v-for="(shortcut, id) in shortcutsByCategory"
              :key="id"
              class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle hover:border-horus-border-accent transition-colors"
            >
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-medium text-horus-text-primary">{{ shortcut.label }}</h3>
                  <HBadge
                    :variant="shortcut.category === 'voice' ? 'cyan' : 'default'"
                    size="sm"
                  >
                    {{ shortcut.category }}
                  </HBadge>
                </div>
                <p class="text-xs text-horus-text-secondary mt-1">{{ shortcut.description }}</p>
              </div>
              <div class="flex items-center gap-3">
                <button
                  class="px-4 py-2 bg-horus-bg-tertiary border rounded-lg transition-colors group"
                  :class="isRecording && recordingId === id
                    ? 'border-horus-accent-cyan animate-pulse'
                    : 'border-horus-border-subtle hover:border-horus-accent-cyan'"
                  @click="handleStartRecording(id)"
                >
                  <div class="flex items-center gap-2">
                    <kbd class="px-2 py-1 bg-horus-bg-primary border border-horus-border-subtle rounded text-horus-text-primary font-mono text-sm group-hover:border-horus-accent-cyan group-hover:text-horus-accent-cyan transition-colors">
                      {{ getDisplayCombo(id) }}
                    </kbd>
                    <Icon
                      :name="isRecording && recordingId === id ? 'heroicons:signal' : 'heroicons:pencil'"
                      class="w-4 h-4 text-horus-text-muted group-hover:text-horus-accent-cyan transition-colors"
                    />
                  </div>
                </button>
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
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Radio Effects</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Apply authentic radio static and filters</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="preferences.voice.radio_effects" class="sr-only peer" @change="markDirty">
                <div class="w-11 h-6 bg-horus-bg-tertiary peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-horus-accent-cyan"></div>
              </label>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Preferred Language</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Default language for ATC communication</p>
              </div>
              <div class="w-48">
                <HDropdown
                  v-model="preferences.voice.language"
                  :options="languageOptions"
                  placeholder="Select language"
                  @update:model-value="markDirty"
                />
              </div>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Push-to-Talk Mode</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Choose between hold-to-talk or toggle mode</p>
              </div>
              <select
                v-model="preferences.voice.ptt_mode"
                class="bg-horus-bg-tertiary border border-horus-border-subtle rounded-lg px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                @change="markDirty"
              >
                <option value="hold">Hold to Talk</option>
                <option value="toggle">Toggle (Press to Start/Stop)</option>
              </select>
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
            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Theme Mode</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Switch between dark and light themes</p>
              </div>
              <select
                v-model="preferences.display.theme"
                class="bg-horus-bg-tertiary border border-horus-border-subtle rounded-lg px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                @change="markDirty"
              >
                <option value="dark">Dark Mode</option>
                <option value="light">Light Mode</option>
                <option value="system">System Default</option>
              </select>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Animations</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Enable or disable UI animations</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="preferences.display.animations" class="sr-only peer" @change="markDirty">
                <div class="w-11 h-6 bg-horus-bg-tertiary peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-horus-accent-cyan"></div>
              </label>
            </div>

            <div class="flex items-center justify-between p-4 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">Compact Mode</h3>
                <p class="text-xs text-horus-text-secondary mt-1">Reduce spacing for more content on screen</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="preferences.display.compact_mode" class="sr-only peer" @change="markDirty">
                <div class="w-11 h-6 bg-horus-bg-tertiary peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-horus-accent-cyan"></div>
              </label>
            </div>
          </div>
        </HCard>

        <!-- Actions -->
        <div class="flex items-center justify-between gap-4 pt-4">
          <HButton
            variant="secondary"
            @click="handleResetAll"
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
              :disabled="!isDirty || prefLoading"
              @click="handleSave"
            >
              <Icon v-if="prefLoading" name="heroicons:arrow-path" class="w-4 h-4 animate-spin" />
              <Icon v-else name="heroicons:check" class="w-4 h-4" />
              {{ prefLoading ? 'Saving...' : 'Save Changes' }}
            </HButton>
          </div>
        </div>

        <!-- Save feedback -->
        <Transition
          enter-active-class="transition-all duration-300 ease-out"
          enter-from-class="opacity-0 translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 translate-y-2"
        >
          <div v-if="saveMessage" class="text-center py-2">
            <span :class="saveSuccess ? 'text-horus-status-success' : 'text-horus-status-danger'" class="text-sm">
              {{ saveMessage }}
            </span>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Shortcuts Help Modal -->
    <HShortcutsModal v-model="showShortcutsHelp" />
  </div>
</template>

<script setup lang="ts">
const {
  shortcuts: allShortcuts,
  isRecording,
  recordingId,
  startRecording,
  stopRecording,
  getDisplayCombo,
  resetToDefaults: resetShortcutDefaults,
} = useKeyboardShortcuts()

const {
  preferences,
  isLoading: prefLoading,
  isSynced: prefSynced,
  error: prefError,
  initialize: initPrefs,
  saveToBackend,
  resetToDefaults: resetPrefDefaults,
} = usePreferences()

const isDirty = ref(false)
const showShortcutsHelp = ref(false)
const saveMessage = ref<string | null>(null)
const saveSuccess = ref(false)

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish (Español)' },
  { value: 'fr', label: 'French (Français)' },
  { value: 'de', label: 'German (Deutsch)' },
]

// Filter shortcuts to show editable ones
const shortcutsByCategory = computed(() => {
  const editable: Record<string, { label: string; description: string; category: string }> = {}
  for (const [id, binding] of Object.entries(allShortcuts.value)) {
    if (id !== 'escape') {
      editable[id] = binding
    }
  }
  return editable
})

function markDirty(): void {
  isDirty.value = true
}

function handleStartRecording(id: string): void {
  if (isRecording.value && recordingId.value === id) {
    stopRecording()
  } else {
    startRecording(id)
    markDirty()
  }
}

async function handleSave(): Promise<void> {
  const success = await saveToBackend()
  isDirty.value = false
  saveSuccess.value = success
  saveMessage.value = success
    ? 'Settings saved and synced to your account!'
    : 'Settings saved locally (backend sync failed)'

  setTimeout(() => { saveMessage.value = null }, 3000)
}

async function handleResetAll(): Promise<void> {
  resetShortcutDefaults()
  await resetPrefDefaults()
  isDirty.value = false
  saveMessage.value = 'All settings reset to defaults'
  saveSuccess.value = true
  setTimeout(() => { saveMessage.value = null }, 3000)
}

onMounted(async () => {
  await initPrefs()
})
</script>
