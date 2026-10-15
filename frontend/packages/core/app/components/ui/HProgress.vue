<script setup lang="ts">
interface Props {
  value: number
  max?: number
  label?: string
  showPercentage?: boolean
  variant?: 'default' | 'success' | 'warning' | 'danger'
  size?: 'sm' | 'md'
  animated?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  max: 100,
  showPercentage: true,
  variant: 'default',
  size: 'md',
  animated: true,
})

const percentage = computed(() => {
  return Math.min(100, Math.max(0, (props.value / props.max) * 100))
})

const fillColorClass = computed(() => {
  if (props.variant !== 'default') {
    switch (props.variant) {
      case 'success': return 'bg-horus-status-success'
      case 'warning': return 'bg-horus-status-warning'
      case 'danger': return 'bg-horus-status-danger'
    }
  }
  // Auto-color based on percentage
  if (percentage.value >= 75) return 'bg-horus-status-success'
  if (percentage.value >= 40) return 'bg-horus-accent-cyan'
  if (percentage.value >= 20) return 'bg-horus-status-warning'
  return 'bg-horus-status-danger'
})

const heightClass = computed(() => {
  return props.size === 'sm' ? 'h-1' : 'h-1.5'
})
</script>

<template>
  <div class="space-y-1.5">
    <div
      v-if="label || showPercentage"
      class="flex items-center justify-between text-xs"
    >
      <span
        v-if="label"
        class="text-horus-text-muted uppercase tracking-wider"
      >{{ label }}</span>
      <span
        v-if="showPercentage"
        class="font-mono text-horus-text-secondary"
      >{{ Math.round(percentage) }}% COMPLETE</span>
    </div>

    <div :class="['w-full bg-horus-bg-secondary rounded-full overflow-hidden', heightClass]">
      <div
        :class="[
          'h-full rounded-full',
          fillColorClass,
          animated && 'transition-all duration-500 ease-out',
        ]"
        :style="{ width: `${percentage}%` }"
      />
    </div>
  </div>
</template>
