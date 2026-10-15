<script setup lang="ts">
defineOptions({
  name: 'AppSettingsWorkspace',
})

const props = withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    backTo?: string
    cancelLabel?: string
    shortcutsDescription?: string
    voiceDescription?: string
    displayDescription?: string
    saveSuccessMessage?: string
    saveLocalOnlyMessage?: string
    resetMessage?: string
  }>(),
  {
    title: 'Settings',
    subtitle: 'CONFIGURE YOUR EXPERIENCE',
    backTo: '/dashboard',
    cancelLabel: 'Cancel',
    shortcutsDescription: 'Customize hotkeys for quick actions',
    voiceDescription: 'Configure ATC voice settings',
    displayDescription: 'Customize visual preferences',
    saveSuccessMessage: 'Settings saved and synced to your account!',
    saveLocalOnlyMessage: 'Settings saved locally (backend sync failed)',
    resetMessage: 'All settings reset to defaults',
  },
)

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
  { value: 'es', label: 'Spanish (Espanol)' },
  { value: 'fr', label: 'French (Français)' },
  { value: 'de', label: 'German (Deutsch)' },
]

const shortcutsByCategory = computed(() => {
  const editable: Record<string, { label: string, description: string, category: string }> = {}
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
  }
  else {
    startRecording(id)
    markDirty()
  }
}

async function handleSave(): Promise<void> {
  const success = await saveToBackend()
  isDirty.value = false
  saveSuccess.value = success
  saveMessage.value = success ? props.saveSuccessMessage : props.saveLocalOnlyMessage

  setTimeout(() => {
    saveMessage.value = null
  }, 3000)
}

async function handleResetAll(): Promise<void> {
  resetShortcutDefaults()
  await resetPrefDefaults()
  isDirty.value = false
  saveMessage.value = props.resetMessage
  saveSuccess.value = true
  setTimeout(() => {
    saveMessage.value = null
  }, 3000)
}

onMounted(async () => {
  await initPrefs()
})
</script>

<template>
  <div class="min-h-screen bg-horus-bg-primary">
    <header class="sticky top-0 z-40 border-b border-horus-border-subtle bg-horus-bg-primary/95 backdrop-blur-md">
      <div class="flex h-14 items-center justify-between px-4 lg:px-6">
        <div class="flex items-center gap-4">
          <NuxtLink
            :to="props.backTo"
            class="-ml-2 p-2 text-horus-text-secondary transition-colors hover:text-horus-text-primary"
          >
            <Icon
              name="heroicons:arrow-left"
              class="h-5 w-5"
            />
          </NuxtLink>
          <div>
            <h1 class="text-sm font-semibold text-horus-text-primary">
              {{ props.title }}
            </h1>
            <p class="text-xxs tracking-wider text-horus-text-muted">
              {{ props.subtitle }}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="prefSynced"
            class="flex items-center gap-1 text-xs text-horus-status-success"
          >
            <Icon
              name="heroicons:check-circle"
              class="h-4 w-4"
            />
            Synced
          </span>
          <span
            v-else-if="prefError"
            class="flex items-center gap-1 text-xs text-horus-status-warning"
          >
            <Icon
              name="heroicons:exclamation-triangle"
              class="h-4 w-4"
            />
            Local only
          </span>
        </div>
      </div>
    </header>

    <div class="mx-auto max-w-5xl px-4 py-8 lg:px-6">
      <div class="space-y-6">
        <HCard>
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-horus-accent-cyan/20">
                  <Icon
                    name="heroicons:command-line"
                    class="h-6 w-6 text-horus-accent-cyan"
                  />
                </div>
                <div>
                  <h2 class="text-lg font-semibold text-horus-text-primary">
                    Keyboard Shortcuts
                  </h2>
                  <p class="text-sm text-horus-text-secondary">
                    {{ props.shortcutsDescription }}
                  </p>
                </div>
              </div>
              <button
                class="flex items-center gap-1 text-xs text-horus-text-muted transition-colors hover:text-horus-accent-cyan"
                @click="showShortcutsHelp = true"
              >
                <Icon
                  name="heroicons:question-mark-circle"
                  class="h-4 w-4"
                />
                View All (Ctrl+/)
              </button>
            </div>
          </template>

          <div class="space-y-3">
            <div
              v-for="(shortcut, id) in shortcutsByCategory"
              :key="id"
              class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4 transition-colors hover:border-horus-border-accent"
            >
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-medium text-horus-text-primary">
                    {{ shortcut.label }}
                  </h3>
                  <HBadge
                    :variant="shortcut.category === 'voice' ? 'cyan' : 'default'"
                    size="sm"
                  >
                    {{ shortcut.category }}
                  </HBadge>
                </div>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  {{ shortcut.description }}
                </p>
              </div>
              <div class="flex items-center gap-3">
                <button
                  class="group rounded-lg border bg-horus-bg-tertiary px-4 py-2 transition-colors"
                  :class="isRecording && recordingId === id
                    ? 'animate-pulse border-horus-accent-cyan'
                    : 'border-horus-border-subtle hover:border-horus-accent-cyan'"
                  @click="handleStartRecording(id)"
                >
                  <div class="flex items-center gap-2">
                    <kbd class="rounded border border-horus-border-subtle bg-horus-bg-primary px-2 py-1 font-mono text-sm text-horus-text-primary transition-colors group-hover:border-horus-accent-cyan group-hover:text-horus-accent-cyan">
                      {{ getDisplayCombo(id) }}
                    </kbd>
                    <Icon
                      :name="isRecording && recordingId === id ? 'heroicons:signal' : 'heroicons:pencil'"
                      class="h-4 w-4 text-horus-text-muted transition-colors group-hover:text-horus-accent-cyan"
                    />
                  </div>
                </button>
              </div>
            </div>
          </div>
        </HCard>

        <HCard>
          <template #header>
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-horus-status-info/20">
                <Icon
                  name="heroicons:microphone"
                  class="h-6 w-6 text-horus-status-info"
                />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-horus-text-primary">
                  Voice Communication
                </h2>
                <p class="text-sm text-horus-text-secondary">
                  {{ props.voiceDescription }}
                </p>
              </div>
            </div>
          </template>

          <div class="space-y-4">
            <div class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">
                  Radio Effects
                </h3>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  Apply authentic radio static and filters
                </p>
              </div>
              <label class="relative inline-flex cursor-pointer items-center">
                <input
                  v-model="preferences.voice.radio_effects"
                  type="checkbox"
                  class="peer sr-only"
                  @change="markDirty"
                >
                <div class="peer h-6 w-11 rounded-full bg-horus-bg-tertiary after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-horus-accent-cyan peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan" />
              </label>
            </div>

            <div class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">
                  Preferred Language
                </h3>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  Default language for ATC communication
                </p>
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

            <div class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">
                  Push-to-Talk Mode
                </h3>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  Choose between hold-to-talk or toggle mode
                </p>
              </div>
              <select
                v-model="preferences.voice.ptt_mode"
                class="rounded-lg border border-horus-border-subtle bg-horus-bg-tertiary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                @change="markDirty"
              >
                <option value="hold">
                  Hold to Talk
                </option>
                <option value="toggle">
                  Toggle (Press to Start/Stop)
                </option>
              </select>
            </div>
          </div>
        </HCard>

        <HCard>
          <template #header>
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-horus-status-warning/20">
                <Icon
                  name="heroicons:computer-desktop"
                  class="h-6 w-6 text-horus-status-warning"
                />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-horus-text-primary">
                  Display Settings
                </h2>
                <p class="text-sm text-horus-text-secondary">
                  {{ props.displayDescription }}
                </p>
              </div>
            </div>
          </template>

          <div class="space-y-4">
            <div class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">
                  Theme Mode
                </h3>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  Switch between dark and light themes
                </p>
              </div>
              <select
                v-model="preferences.display.theme"
                class="rounded-lg border border-horus-border-subtle bg-horus-bg-tertiary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                @change="markDirty"
              >
                <option value="dark">
                  Dark Mode
                </option>
                <option value="light">
                  Light Mode
                </option>
                <option value="system">
                  System Default
                </option>
              </select>
            </div>

            <div class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">
                  Animations
                </h3>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  Enable or disable UI animations
                </p>
              </div>
              <label class="relative inline-flex cursor-pointer items-center">
                <input
                  v-model="preferences.display.animations"
                  type="checkbox"
                  class="peer sr-only"
                  @change="markDirty"
                >
                <div class="peer h-6 w-11 rounded-full bg-horus-bg-tertiary after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-horus-accent-cyan peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan" />
              </label>
            </div>

            <div class="flex items-center justify-between rounded-lg border border-horus-border-subtle bg-horus-bg-secondary p-4">
              <div class="flex-1">
                <h3 class="text-sm font-medium text-horus-text-primary">
                  Compact Mode
                </h3>
                <p class="mt-1 text-xs text-horus-text-secondary">
                  Reduce spacing for more content on screen
                </p>
              </div>
              <label class="relative inline-flex cursor-pointer items-center">
                <input
                  v-model="preferences.display.compact_mode"
                  type="checkbox"
                  class="peer sr-only"
                  @change="markDirty"
                >
                <div class="peer h-6 w-11 rounded-full bg-horus-bg-tertiary after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-horus-accent-cyan peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-horus-accent-cyan" />
              </label>
            </div>
          </div>
        </HCard>

        <div class="flex items-center justify-between gap-4 pt-4">
          <HButton
            variant="secondary"
            @click="handleResetAll"
          >
            <Icon
              name="heroicons:arrow-path"
              class="h-4 w-4"
            />
            Reset All to Defaults
          </HButton>
          <div class="flex items-center gap-3">
            <NuxtLink :to="props.backTo">
              <HButton variant="secondary">
                {{ props.cancelLabel }}
              </HButton>
            </NuxtLink>
            <HButton
              variant="primary"
              :disabled="!isDirty || prefLoading"
              @click="handleSave"
            >
              <Icon
                v-if="prefLoading"
                name="heroicons:arrow-path"
                class="h-4 w-4 animate-spin"
              />
              <Icon
                v-else
                name="heroicons:check"
                class="h-4 w-4"
              />
              {{ prefLoading ? 'Saving...' : 'Save Changes' }}
            </HButton>
          </div>
        </div>

        <Transition
          enter-active-class="transition-all duration-300 ease-out"
          enter-from-class="translate-y-2 opacity-0"
          enter-to-class="translate-y-0 opacity-100"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="translate-y-0 opacity-100"
          leave-to-class="translate-y-2 opacity-0"
        >
          <div
            v-if="saveMessage"
            class="py-2 text-center"
          >
            <span
              class="text-sm"
              :class="saveSuccess ? 'text-horus-status-success' : 'text-horus-status-danger'"
            >
              {{ saveMessage }}
            </span>
          </div>
        </Transition>
      </div>
    </div>

    <HShortcutsModal v-model="showShortcutsHelp" />
  </div>
</template>
