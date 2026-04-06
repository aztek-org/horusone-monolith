<script setup lang="ts">
interface Option {
  value: string
  label: string
  icon?: string
}

interface Props {
  modelValue: string
  options: Option[]
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md'
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const sizeClasses = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm'
}
</script>

<template>
  <div class="inline-flex rounded-lg bg-horus-bg-secondary p-1 gap-1">
    <button
      v-for="option in options"
      :key="option.value"
      :class="[
        'flex items-center gap-1.5 rounded-md font-medium transition-all duration-200',
        sizeClasses[size],
        modelValue === option.value
          ? 'bg-horus-accent-cyan text-horus-bg-primary shadow-sm'
          : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary'
      ]"
      @click="emit('update:modelValue', option.value)"
    >
      <Icon v-if="option.icon" :name="option.icon" class="w-4 h-4" />
      {{ option.label }}
    </button>
  </div>
</template>
