<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary' | 'danger' | 'success' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  icon?: string
  iconPosition?: 'left' | 'right'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  iconPosition: 'left',
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const variantClasses = {
  primary: 'bg-horus-accent-cyan text-horus-bg-primary hover:bg-horus-accent-cyan-glow focus:ring-horus-accent-cyan shadow-glow-cyan/30',
  secondary: 'bg-horus-bg-tertiary text-horus-text-primary border border-horus-border-default hover:bg-horus-bg-elevated hover:border-horus-accent-cyan/50',
  danger: 'bg-horus-status-danger text-white hover:bg-horus-status-danger-dim focus:ring-horus-status-danger',
  success: 'bg-horus-status-success text-white hover:bg-horus-status-success-dim focus:ring-horus-status-success',
  ghost: 'bg-transparent text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary',
}

const sizeClasses = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

function handleClick(event: MouseEvent) {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<template>
  <button
    :class="[
      'inline-flex items-center justify-center gap-2 font-medium rounded-md transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-horus-bg-primary',
      variantClasses[variant],
      sizeClasses[size],
      (disabled || loading) && 'opacity-50 cursor-not-allowed',
    ]"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <Icon
      v-if="loading"
      name="svg-spinners:ring-resize"
      class="w-4 h-4"
    />
    <template v-else>
      <Icon
        v-if="icon && iconPosition === 'left'"
        :name="icon"
        class="w-4 h-4"
      />
      <slot />
      <Icon
        v-if="icon && iconPosition === 'right'"
        :name="icon"
        class="w-4 h-4"
      />
    </template>
  </button>
</template>
