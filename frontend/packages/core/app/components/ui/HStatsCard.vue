<script setup lang="ts">
interface Props {
  label: string
  value: string | number
  icon?: string
  trend?: 'up' | 'down' | 'stable'
  trendValue?: string
  unit?: string
}

const props = withDefaults(defineProps<Props>(), {
  trend: 'stable',
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
</script>

<template>
  <HCard
    variant="default"
    padding="md"
  >
    <div class="flex items-start gap-3">
      <div
        v-if="icon"
        class="w-10 h-10 rounded-lg bg-horus-accent-cyan/10 flex items-center justify-center flex-shrink-0"
      >
        <Icon
          :name="icon"
          class="w-5 h-5 text-horus-accent-cyan"
        />
      </div>

      <div class="flex-1 min-w-0">
        <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
          {{ label }}
        </p>

        <div class="flex items-baseline gap-1.5 mt-1">
          <span class="text-2xl font-bold text-horus-text-primary font-mono">
            {{ value }}
          </span>
          <span
            v-if="unit"
            class="text-xs text-horus-text-secondary"
          >
            {{ unit }}
          </span>
        </div>

        <div
          v-if="trend && trend !== 'stable'"
          class="flex items-center gap-1 mt-1.5"
        >
          <Icon
            :name="trendIcon"
            :class="['w-4 h-4', trendColor]"
          />
          <span
            v-if="trendValue"
            :class="['text-xs font-mono', trendColor]"
          >
            {{ trendValue }}
          </span>
        </div>
      </div>
    </div>
  </HCard>
</template>
