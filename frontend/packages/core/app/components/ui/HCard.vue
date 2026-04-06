<script setup lang="ts">
interface Props {
  variant?: 'elevated' | 'glass' | 'default'
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  padding: 'md',
  hover: false
})

const variantClasses = {
  default: 'bg-horus-bg-card/80 backdrop-blur-sm border-horus-border-subtle',
  elevated: 'bg-horus-bg-elevated/90 backdrop-blur-md border-horus-border-subtle shadow-card-elevated',
  glass: 'bg-gradient-to-br from-horus-bg-tertiary/50 to-horus-bg-card/30 backdrop-blur-lg border-horus-border-subtle/50',
}

const paddingClasses = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}
</script>

<template>
  <div
    :class="[
      'border rounded-lg transition-all duration-200',
      variantClasses[variant],
      paddingClasses[padding],
      hover && 'hover:border-horus-accent-cyan/30 hover:shadow-glow-cyan/10'
    ]"
  >
    <slot />
  </div>
</template>
