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
        v-if="isOpen"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        @click.self="close"
      >
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition-all duration-150 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="isOpen"
            class="bg-horus-bg-elevated border border-horus-border-accent rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
          >
            <!-- Header -->
            <div class="sticky top-0 bg-horus-bg-elevated border-b border-horus-border-subtle px-6 py-4 flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
                  <Icon name="heroicons:paper-airplane" class="w-6 h-6 text-horus-accent-cyan" />
                </div>
                <div>
                  <h2 class="text-lg font-semibold text-horus-text-primary">About Horus MVP</h2>
                  <p class="text-xs text-horus-text-muted">Aviation Training Platform</p>
                </div>
              </div>
              <button
                @click="close"
                class="p-2 rounded-lg text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
              >
                <Icon name="heroicons:x-mark" class="w-5 h-5" />
              </button>
            </div>

            <!-- Content -->
            <div class="p-6 space-y-6">
              <!-- Version Info -->
              <HSection title="Version Information">
                <div class="space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-horus-text-secondary">Application Version</span>
                    <HBadge variant="cyan">v4.0.0-beta</HBadge>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-horus-text-secondary">Build Date</span>
                    <span class="text-sm text-horus-text-primary">February 20, 2026</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-horus-text-secondary">Environment</span>
                    <HBadge variant="success">Development</HBadge>
                  </div>
                </div>
              </HSection>

              <!-- Tech Stack -->
              <HSection title="Technology Stack">
                <div class="space-y-4">
                  <!-- Frontend -->
                  <div>
                    <h4 class="text-xs font-semibold text-horus-text-muted uppercase tracking-wider mb-2">Frontend</h4>
                    <div class="flex flex-wrap gap-2">
                      <HBadge variant="default">Nuxt.js 4.x</HBadge>
                      <HBadge variant="default">Vue 3</HBadge>
                      <HBadge variant="default">TypeScript</HBadge>
                      <HBadge variant="default">TailwindCSS 3.x</HBadge>
                    </div>
                  </div>

                  <!-- Backend -->
                  <div>
                    <h4 class="text-xs font-semibold text-horus-text-muted uppercase tracking-wider mb-2">Backend</h4>
                    <div class="flex flex-wrap gap-2">
                      <HBadge variant="default">FastAPI</HBadge>
                      <HBadge variant="default">Python 3.10+</HBadge>
                      <HBadge variant="default">WebSockets</HBadge>
                    </div>
                  </div>

                  <!-- AI Services -->
                  <div>
                    <h4 class="text-xs font-semibold text-horus-text-muted uppercase tracking-wider mb-2">AI Services</h4>
                    <div class="space-y-2">
                      <div class="flex justify-between items-center">
                        <span class="text-sm text-horus-text-secondary">Speech-to-Text</span>
                        <HBadge variant="cyan">OpenAI Whisper</HBadge>
                      </div>
                      <div class="flex justify-between items-center">
                        <span class="text-sm text-horus-text-secondary">Language Model</span>
                        <HBadge variant="cyan">Ollama (LLaMA 3.2:3b)</HBadge>
                      </div>
                      <div class="flex justify-between items-center">
                        <span class="text-sm text-horus-text-secondary">Text-to-Speech</span>
                        <HBadge variant="cyan">Google TTS</HBadge>
                      </div>
                      <div class="flex justify-between items-center">
                        <span class="text-sm text-horus-text-secondary">Audio Effects</span>
                        <HBadge variant="cyan">SciPy Filters</HBadge>
                      </div>
                    </div>
                  </div>
                </div>
              </HSection>

              <!-- Features -->
              <HSection title="Key Features">
                <ul class="space-y-2 text-sm text-horus-text-secondary">
                  <li class="flex items-start gap-2">
                    <Icon name="heroicons:check-circle-solid" class="w-5 h-5 text-horus-status-success flex-shrink-0 mt-0.5" />
                    <span>Real-time bi-directional voice communication with ATC</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <Icon name="heroicons:check-circle-solid" class="w-5 h-5 text-horus-status-success flex-shrink-0 mt-0.5" />
                    <span>Multi-language support (English & Spanish)</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <Icon name="heroicons:check-circle-solid" class="w-5 h-5 text-horus-status-success flex-shrink-0 mt-0.5" />
                    <span>AI-powered ATC agent with ICAO phraseology</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <Icon name="heroicons:check-circle-solid" class="w-5 h-5 text-horus-status-success flex-shrink-0 mt-0.5" />
                    <span>Authentic radio effects and audio processing</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <Icon name="heroicons:check-circle-solid" class="w-5 h-5 text-horus-status-success flex-shrink-0 mt-0.5" />
                    <span>Interactive scenario architect and route planning</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <Icon name="heroicons:check-circle-solid" class="w-5 h-5 text-horus-status-success flex-shrink-0 mt-0.5" />
                    <span>Performance analytics and flight metrics tracking</span>
                  </li>
                </ul>
              </HSection>

              <!-- License -->
              <HSection title="License & Credits">
                <div class="space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-horus-text-secondary">License</span>
                    <HBadge variant="default">MIT License</HBadge>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-horus-text-secondary">Repository</span>
                    <a href="#" class="text-sm text-horus-accent-cyan hover:underline">GitHub</a>
                  </div>
                  <p class="text-xs text-horus-text-muted pt-3 border-t border-horus-border-subtle">
                    Built with ❤️ for aviation training and simulation. This is a development preview and should not be used for real flight operations.
                  </p>
                </div>
              </HSection>
            </div>

            <!-- Footer -->
            <div class="sticky bottom-0 bg-horus-bg-elevated border-t border-horus-border-subtle px-6 py-4">
              <HButton
                variant="secondary"
                class="w-full"
                @click="close"
              >
                Close
              </HButton>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  modelValue: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const isOpen = ref(props.modelValue)

watch(() => props.modelValue, (newValue) => {
  isOpen.value = newValue
})

function close() {
  isOpen.value = false
  emit('update:modelValue', false)
}
</script>
