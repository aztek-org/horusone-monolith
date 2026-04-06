<script setup lang="ts">
interface Props {
  variant?: 'active' | 'idle' | 'warning' | 'danger' | 'info' | 'mod' | 'default' | 'success' | 'cyan'
  size?: 'sm' | 'md'
  pulse?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'active',
  size: 'md',
  pulse: false
})

const variantClasses = {
  active: 'bg-horus-status-success/20 text-horus-status-success border-horus-status-success/30',
  success: 'bg-horus-status-success/20 text-horus-status-success border-horus-status-success/30',
  idle: 'bg-horus-text-muted/20 text-horus-text-muted border-horus-text-muted/30',
  warning: 'bg-horus-status-warning/20 text-horus-status-warning border-horus-status-warning/30',
  danger: 'bg-horus-status-danger/20 text-horus-status-danger border-horus-status-danger/30',
  info: 'bg-horus-accent-cyan/20 text-horus-accent-cyan border-horus-accent-cyan/30',
  cyan: 'bg-horus-accent-cyan/20 text-horus-accent-cyan border-horus-accent-cyan/30',
  mod: 'bg-horus-status-info/20 text-horus-status-info border-horus-status-info/30',
  default: 'bg-horus-bg-tertiary text-horus-text-secondary border-horus-border-subtle',
}

const sizeClasses = {
  sm: 'px-1.5 py-0.5 text-xxs',
  md: 'px-2 py-0.5 text-xxs',
}
</script>

<template>
  <span
    :class="[
      'inline-flex items-center font-semibold uppercase tracking-wider rounded border',
      variantClasses[variant],
      sizeClasses[size],
      pulse && 'animate-pulse-slow'
    ]"
  >
    <span v-if="pulse" class="w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-pulse" />
    <slot />
  </span>
</template>
