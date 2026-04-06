<script setup lang="ts">
import type { VoiceLog } from '~/composables/useSessionReplay'

interface Props {
  voiceLogs: VoiceLog[]
  currentTimestamp: string
  currentIndex: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'jump-to': [log: VoiceLog]
}>()

const scrollContainer = ref<HTMLElement | null>(null)

const speakerConfig: Record<string, { prefix: string; color: string; bgColor: string; icon: string }> = {
  pilot: {
    prefix: 'PILOT',
    color: 'text-horus-status-success',
    bgColor: 'bg-horus-status-success/5 border-horus-status-success/20',
    icon: 'heroicons:microphone',
  },
  atc: {
    prefix: 'ATC',
    color: 'text-horus-accent-cyan',
    bgColor: 'bg-horus-accent-cyan/5 border-horus-accent-cyan/20',
    icon: 'heroicons:signal',
  },
  system: {
    prefix: 'SYS',
    color: 'text-horus-status-warning',
    bgColor: 'bg-horus-status-warning/5 border-horus-status-warning/20',
    icon: 'heroicons:cpu-chip',
  },
}

function getSpeakerConfig(speaker: string) {
  return speakerConfig[speaker] ?? speakerConfig.system
}

function isActiveEntry(log: VoiceLog): boolean {
  return log.track_index <= props.currentIndex
    && (log.track_index >= props.currentIndex - 5)
}

function isFutureEntry(log: VoiceLog): boolean {
  return log.track_index > props.currentIndex
}

// Auto-scroll to the latest active entry
watch(
  () => props.currentIndex,
  () => {
    nextTick(() => {
      if (!scrollContainer.value) return
      const activeEl = scrollContainer.value.querySelector('[data-active="true"]')
      if (activeEl) {
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    })
  },
)

function formatTime(timestamp: string): string {
  if (!timestamp) return '--:--'
  // If ISO, extract HH:MM:SS
  if (timestamp.includes('T')) {
    return timestamp.split('T')[1]?.substring(0, 8) ?? timestamp
  }
  return timestamp
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center gap-2 pb-3 border-b border-horus-border-subtle mb-3 shrink-0">
      <Icon name="heroicons:chat-bubble-left-right" class="w-4 h-4 text-horus-accent-cyan" />
      <h3 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider">
        Voice Transcript
      </h3>
      <span class="ml-auto text-xxs text-horus-text-muted font-mono">
        {{ voiceLogs.length }} entries
      </span>
    </div>

    <!-- Empty State -->
    <div v-if="voiceLogs.length === 0" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <Icon name="heroicons:chat-bubble-left-ellipsis" class="w-8 h-8 text-horus-text-muted mx-auto mb-2 opacity-50" />
        <p class="text-xs text-horus-text-muted">No voice logs available</p>
      </div>
    </div>

    <!-- Transcript List -->
    <div
      v-else
      ref="scrollContainer"
      class="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin"
    >
      <button
        v-for="log in voiceLogs"
        :key="log.id"
        :data-active="isActiveEntry(log)"
        :class="[
          'w-full text-left p-2.5 rounded-lg border transition-all duration-200',
          isActiveEntry(log)
            ? getSpeakerConfig(log.speaker).bgColor
            : isFutureEntry(log)
              ? 'bg-horus-bg-primary/30 border-horus-border-subtle/50 opacity-40'
              : 'bg-horus-bg-card/50 border-horus-border-subtle hover:border-horus-accent-cyan/30',
        ]"
        @click="emit('jump-to', log)"
      >
        <div class="flex items-center gap-2 mb-1">
          <Icon
            :name="getSpeakerConfig(log.speaker).icon"
            :class="['w-3.5 h-3.5', getSpeakerConfig(log.speaker).color]"
          />
          <span :class="['text-xxs font-semibold uppercase tracking-wider', getSpeakerConfig(log.speaker).color]">
            {{ getSpeakerConfig(log.speaker).prefix }}
          </span>
          <span class="ml-auto text-xxs font-mono text-horus-text-muted">
            {{ formatTime(log.timestamp) }}
          </span>
        </div>
        <p
          :class="[
            'text-xs leading-relaxed',
            isFutureEntry(log) ? 'text-horus-text-muted' : 'text-horus-text-secondary',
          ]"
        >
          {{ log.message }}
        </p>
        <div v-if="log.frequency" class="mt-1 flex items-center gap-2">
          <span class="text-xxs font-mono text-horus-text-muted">
            {{ log.frequency }}
          </span>
          <div v-if="log.quality_score !== null" class="flex items-center gap-1">
            <div
              :class="[
                'w-1.5 h-1.5 rounded-full',
                log.quality_score >= 80 ? 'bg-horus-status-success' :
                log.quality_score >= 50 ? 'bg-horus-status-warning' :
                'bg-horus-status-danger'
              ]"
            />
            <span class="text-xxs font-mono text-horus-text-muted">{{ log.quality_score }}%</span>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-thin::-webkit-scrollbar {
  width: 4px;
}

.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}

.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.3);
  border-radius: 2px;
}

.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.5);
}
</style>
