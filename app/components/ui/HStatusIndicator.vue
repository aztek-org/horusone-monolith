<script setup lang="ts">
interface Props {
  status: 'nominal' | 'warning' | 'critical' | 'offline'
  label: string
  value?: string
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md'
})

const statusConfig = {
  nominal: {
    bgClass: 'bg-horus-status-success/10',
    textClass: 'text-horus-status-success',
    dotClass: 'bg-horus-status-success',
    borderClass: 'border-horus-status-success/30'
  },
  warning: {
    bgClass: 'bg-horus-status-warning/10',
    textClass: 'text-horus-status-warning',
    dotClass: 'bg-horus-status-warning',
    borderClass: 'border-horus-status-warning/30'
  },
  critical: {
    bgClass: 'bg-horus-status-danger/10',
    textClass: 'text-horus-status-danger',
    dotClass: 'bg-horus-status-danger animate-pulse',
    borderClass: 'border-horus-status-danger/30'
  },
  offline: {
    bgClass: 'bg-horus-text-muted/10',
    textClass: 'text-horus-text-muted',
    dotClass: 'bg-horus-text-muted',
    borderClass: 'border-horus-text-muted/30'
  }
}

const config = computed(() => statusConfig[props.status])
</script>

<template>
  <div
    :class="[
      'rounded-lg border p-3',
      config.bgClass,
      config.borderClass
    ]"
  >
    <div class="flex items-center justify-between gap-2">
      <span class="text-xxs uppercase tracking-wider text-horus-text-muted">
        {{ label }}
      </span>
      <span :class="['w-2 h-2 rounded-full', config.dotClass]" />
    </div>
    <p v-if="value" :class="['text-sm font-semibold mt-1', config.textClass]">
      {{ value }}
    </p>
  </div>
</template>
