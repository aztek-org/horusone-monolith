<script setup lang="ts">
interface Props {
  online?: boolean
  label?: string
  variant?: 'default' | 'success' | 'warning' | 'danger'
}

const props = withDefaults(defineProps<Props>(), {
  online: true,
  variant: 'default'
})

const dotClass = computed(() => {
  if (!props.online) return 'bg-horus-text-muted'
  switch (props.variant) {
    case 'success': return 'bg-horus-status-success'
    case 'warning': return 'bg-horus-status-warning'
    case 'danger': return 'bg-horus-status-danger'
    default: return 'bg-horus-status-success'
  }
})

const textClass = computed(() => {
  if (!props.online) return 'text-horus-text-muted'
  switch (props.variant) {
    case 'success': return 'text-horus-status-success'
    case 'warning': return 'text-horus-status-warning'
    case 'danger': return 'text-horus-status-danger'
    default: return 'text-horus-text-primary'
  }
})
</script>

<template>
  <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-horus-bg-secondary/80 border border-horus-border-subtle">
    <span :class="['w-2 h-2 rounded-full', dotClass, online && 'animate-pulse']" />
    <span v-if="label" :class="['text-xs font-medium', textClass]">
      {{ label }}
    </span>
    <slot v-else />
  </div>
</template>
