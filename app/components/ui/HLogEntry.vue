<script setup lang="ts">
interface Props {
  timestamp?: string
  type?: 'ai' | 'user' | 'system' | 'atc'
  variant?: 'default' | 'warning' | 'info'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'system',
  variant: 'default'
})

const typeConfig = {
  ai: { prefix: 'AI:', color: 'text-horus-accent-cyan' },
  user: { prefix: 'USER:', color: 'text-horus-status-success' },
  system: { prefix: 'SYS:', color: 'text-horus-status-warning' },
  atc: { prefix: 'ATC:', color: 'text-horus-text-secondary' }
}

const config = computed(() => typeConfig[props.type])

const variantClass = computed(() => {
  switch (props.variant) {
    case 'warning': return 'text-horus-status-warning'
    case 'info': return 'text-horus-accent-cyan'
    default: return 'text-horus-text-secondary'
  }
})
</script>

<template>
  <div class="flex gap-2 text-xs font-mono">
    <span v-if="timestamp" class="text-horus-text-muted shrink-0">[{{ timestamp }}]</span>
    <span :class="['shrink-0', config.color]">{{ config.prefix }}</span>
    <span :class="['flex-1', variant === 'default' ? 'text-horus-text-secondary' : variantClass]">
      <slot />
    </span>
  </div>
</template>
