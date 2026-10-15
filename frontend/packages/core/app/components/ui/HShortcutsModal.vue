<script setup lang="ts">
/**
 * HShortcutsModal — Keyboard shortcuts reference overlay.
 * Displays all registered shortcuts grouped by category.
 * Toggle with Ctrl+/ or programmatically via v-model.
 */

interface Props {
  modelValue: boolean
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const { shortcuts, getDisplayCombo } = useKeyboardShortcuts()

// ---------------------------------------------------------------------------
// Derived data
// ---------------------------------------------------------------------------

interface CategoryGroup {
  key: 'voice' | 'navigation' | 'general'
  label: string
  icon: string
  items: { id: string, label: string, description: string, combo: string, enabled: boolean }[]
}

const categories = computed<CategoryGroup[]>(() => {
  const groups: Record<string, CategoryGroup> = {
    voice: { key: 'voice', label: 'Voice', icon: 'heroicons:microphone', items: [] },
    navigation: { key: 'navigation', label: 'Navigation', icon: 'heroicons:map', items: [] },
    general: { key: 'general', label: 'General', icon: 'heroicons:cog-6-tooth', items: [] },
  }

  for (const [id, binding] of Object.entries(shortcuts.value)) {
    const group = groups[binding.category]
    if (!group) continue
    group.items.push({
      id,
      label: binding.label,
      description: binding.description,
      combo: getDisplayCombo(id),
      enabled: binding.enabled,
    })
  }

  // Only return groups that have items
  return Object.values(groups).filter(g => g.items.length > 0)
})

// ---------------------------------------------------------------------------
// Close helpers
// ---------------------------------------------------------------------------

function close(): void {
  emit('update:modelValue', false)
}

function onBackdropClick(): void {
  close()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.code === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    close()
  }
}

// Attach / detach the Escape listener while the modal is open
watch(
  () => props.modelValue,
  (open) => {
    if (import.meta.server) return
    if (open) {
      window.addEventListener('keydown', onKeydown, { capture: true })
    }
    else {
      window.removeEventListener('keydown', onKeydown, { capture: true })
    }
  },
)

onUnmounted(() => {
  if (import.meta.client) {
    window.removeEventListener('keydown', onKeydown, { capture: true })
  }
})
</script>

<template>
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
        v-if="modelValue"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        @click.self="onBackdropClick"
      >
        <!-- Modal panel -->
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 scale-95 translate-y-2"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition-all duration-150 ease-in"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 translate-y-2"
        >
          <div
            v-if="modelValue"
            class="bg-horus-bg-elevated border border-horus-border-subtle rounded-xl shadow-card-elevated max-w-lg w-full max-h-[80vh] flex flex-col overflow-hidden"
          >
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-horus-border-subtle shrink-0">
              <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
                  <Icon
                    name="heroicons:command-line"
                    class="w-5 h-5 text-horus-accent-cyan"
                  />
                </div>
                <div>
                  <h2 class="text-base font-semibold text-horus-text-primary">
                    Keyboard Shortcuts
                  </h2>
                  <p class="text-xxs text-horus-text-muted tracking-wider uppercase">
                    Quick Reference
                  </p>
                </div>
              </div>
              <button
                class="p-2 -mr-2 rounded-lg text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                @click="close"
              >
                <Icon
                  name="heroicons:x-mark"
                  class="w-5 h-5"
                />
              </button>
            </div>

            <!-- Body (scrollable) -->
            <div class="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              <div
                v-for="category in categories"
                :key="category.key"
              >
                <!-- Category heading -->
                <div class="flex items-center gap-2 mb-3">
                  <Icon
                    :name="category.icon"
                    class="w-4 h-4 text-horus-accent-cyan"
                  />
                  <span class="text-xs font-semibold uppercase tracking-wider text-horus-text-secondary">
                    {{ category.label }}
                  </span>
                </div>

                <!-- Shortcut rows -->
                <div class="space-y-1.5">
                  <div
                    v-for="item in category.items"
                    :key="item.id"
                    :class="[
                      'flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors',
                      item.enabled
                        ? 'bg-horus-bg-secondary/60 hover:bg-horus-bg-secondary'
                        : 'bg-horus-bg-secondary/30 opacity-50',
                    ]"
                  >
                    <div class="flex-1 min-w-0 mr-4">
                      <p class="text-sm font-medium text-horus-text-primary truncate">
                        {{ item.label }}
                      </p>
                      <p class="text-xs text-horus-text-muted truncate">
                        {{ item.description }}
                      </p>
                    </div>

                    <!-- Key combo badge(s) -->
                    <div class="flex items-center gap-1 shrink-0">
                      <template
                        v-for="(part, idx) in item.combo.split('+')"
                        :key="idx"
                      >
                        <span
                          v-if="idx > 0"
                          class="text-horus-text-muted text-xs"
                        >+</span>
                        <kbd
                          class="inline-flex items-center justify-center min-w-[1.75rem] h-7 px-2 rounded-md border text-xs font-mono font-medium bg-horus-bg-primary border-horus-border-default text-horus-text-primary shadow-sm"
                        >
                          {{ part }}
                        </kbd>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-6 py-3 border-t border-horus-border-subtle shrink-0">
              <p class="text-xxs text-horus-text-muted text-center">
                Customise shortcuts in
                <NuxtLink
                  to="/settings"
                  class="text-horus-accent-cyan hover:text-horus-accent-cyan-glow transition-colors"
                  @click="close"
                >
                  Settings
                </NuxtLink>
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
