<script setup lang="ts">
interface Props {
  isPlaying: boolean
  currentIndex: number
  totalPoints: number
  speed: number
  currentTimestamp?: string
  progress?: number
}

const props = withDefaults(defineProps<Props>(), {
  currentTimestamp: '--:--',
  progress: 0,
})

const emit = defineEmits<{
  'play': []
  'pause': []
  'stop': []
  'seek': [index: number]
  'speed-change': [speed: number]
}>()

const speeds = [1, 2, 4, 8] as const

const scrubberRef = ref<HTMLElement | null>(null)
const isDragging = ref(false)

function handleScrubberClick(event: MouseEvent) {
  if (!scrubberRef.value || props.totalPoints <= 1) return

  const rect = scrubberRef.value.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
  const index = Math.round(ratio * (props.totalPoints - 1))
  emit('seek', index)
}

function handleScrubberDrag(event: MouseEvent) {
  if (!isDragging.value) return
  handleScrubberClick(event)
}

function startDrag(event: MouseEvent) {
  isDragging.value = true
  handleScrubberClick(event)
  window.addEventListener('mousemove', handleScrubberDrag)
  window.addEventListener('mouseup', stopDrag)
}

function stopDrag() {
  isDragging.value = false
  window.removeEventListener('mousemove', handleScrubberDrag)
  window.removeEventListener('mouseup', stopDrag)
}

const formattedTime = computed(() => {
  return props.currentTimestamp || '--:--'
})

const pointsDisplay = computed(() => {
  return `${props.currentIndex + 1} / ${props.totalPoints}`
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleScrubberDrag)
  window.removeEventListener('mouseup', stopDrag)
})
</script>

<template>
  <div class="space-y-3">
    <!-- Timeline Scrubber -->
    <div
      ref="scrubberRef"
      class="relative w-full h-2 bg-horus-bg-secondary rounded-full cursor-pointer group"
      @mousedown="startDrag"
    >
      <!-- Progress Fill -->
      <div
        class="absolute inset-y-0 left-0 bg-horus-accent-cyan rounded-full transition-[width] duration-75"
        :style="{ width: `${progress}%` }"
      />
      <!-- Scrubber Handle -->
      <div
        class="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-horus-accent-cyan border-2 border-horus-bg-primary shadow-glow-cyan opacity-0 group-hover:opacity-100 transition-opacity"
        :style="{ left: `calc(${progress}% - 8px)` }"
      />
    </div>

    <!-- Controls Row -->
    <div class="flex items-center justify-between gap-4">
      <!-- Playback Buttons -->
      <div class="flex items-center gap-2">
        <!-- Stop -->
        <button
          class="w-8 h-8 rounded-lg bg-horus-bg-tertiary border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors"
          title="Stop"
          @click="emit('stop')"
        >
          <Icon
            name="heroicons:stop-solid"
            class="w-4 h-4"
          />
        </button>

        <!-- Play / Pause -->
        <button
          class="w-10 h-10 rounded-lg bg-horus-accent-cyan/20 border border-horus-accent-cyan/30 flex items-center justify-center text-horus-accent-cyan hover:bg-horus-accent-cyan/30 transition-colors"
          :title="isPlaying ? 'Pause' : 'Play'"
          @click="isPlaying ? emit('pause') : emit('play')"
        >
          <Icon
            :name="isPlaying ? 'heroicons:pause-solid' : 'heroicons:play-solid'"
            class="w-5 h-5"
          />
        </button>
      </div>

      <!-- Time & Point Display -->
      <div class="flex items-center gap-4 text-xs">
        <span class="font-mono text-horus-text-primary">{{ formattedTime }}</span>
        <span class="text-horus-text-muted">{{ pointsDisplay }}</span>
      </div>

      <!-- Speed Selector -->
      <div class="flex items-center gap-1">
        <span class="text-xxs text-horus-text-muted mr-1 uppercase tracking-wider">Speed</span>
        <button
          v-for="s in speeds"
          :key="s"
          :class="[
            'px-2 py-1 rounded text-xs font-mono transition-colors',
            speed === s
              ? 'bg-horus-accent-cyan text-horus-bg-primary'
              : 'bg-horus-bg-tertiary text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-elevated',
          ]"
          @click="emit('speed-change', s)"
        >
          {{ s }}x
        </button>
      </div>
    </div>
  </div>
</template>
