<script setup lang="ts">
interface Props {
  value: string | number
  label?: string
  unit?: string
  trend?: 'up' | 'down' | 'stable'
  trendValue?: string
  variant?: 'default' | 'large' | 'compact'
  highlight?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  highlight: false
})

const trendIcon = computed(() => {
  switch (props.trend) {
    case 'up': return 'heroicons:arrow-trending-up'
    case 'down': return 'heroicons:arrow-trending-down'
    default: return 'heroicons:minus'
  }
})

const trendColor = computed(() => {
  switch (props.trend) {
    case 'up': return 'text-horus-status-success'
    case 'down': return 'text-horus-status-danger'
    default: return 'text-horus-text-muted'
  }
})

const valueSize = computed(() => {
  switch (props.variant) {
    case 'large': return 'text-3xl'
    case 'compact': return 'text-lg'
    default: return 'text-2xl'
  }
})
</script>

<template>
  <div class="space-y-1">
    <p v-if="label" class="text-xxs uppercase tracking-wider text-horus-text-muted">
      {{ label }}
    </p>
    
    <div class="flex items-baseline gap-1">
      <span
        :class="[
          'font-mono font-semibold',
          valueSize,
          highlight ? 'text-horus-accent-cyan' : 'text-horus-text-primary'
        ]"
      >
        {{ value }}
      </span>
      <span v-if="unit" class="text-sm text-horus-text-secondary">{{ unit }}</span>
    </div>
    
    <div v-if="trend || trendValue" class="flex items-center gap-1">
      <Icon v-if="trend" :name="trendIcon" :class="['w-4 h-4', trendColor]" />
      <span v-if="trendValue" :class="['text-xs font-mono', trendColor]">
        {{ trendValue }}
      </span>
    </div>
  </div>
</template>
