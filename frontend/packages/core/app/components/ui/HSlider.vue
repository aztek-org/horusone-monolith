<script setup lang="ts">
interface Props {
  modelValue: number
  min?: number
  max?: number
  step?: number
  label?: string
  showValue?: boolean
  valueFormat?: (value: number) => string
  variant?: 'default' | 'danger' | 'warning' | 'success'
}

const props = withDefaults(defineProps<Props>(), {
  min: 0,
  max: 100,
  step: 1,
  showValue: true,
  variant: 'default'
})

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const percentage = computed(() => {
  return ((props.modelValue - props.min) / (props.max - props.min)) * 100
})

const displayValue = computed(() => {
  if (props.valueFormat) {
    return props.valueFormat(props.modelValue)
  }
  return `${props.modelValue}%`
})

const fillColorClass = computed(() => {
  switch (props.variant) {
    case 'danger': return 'bg-horus-status-danger'
    case 'warning': return 'bg-horus-status-warning'
    case 'success': return 'bg-horus-status-success'
    default: return 'bg-horus-accent-cyan'
  }
})

const valueColorClass = computed(() => {
  switch (props.variant) {
    case 'danger': return 'text-horus-status-danger'
    case 'warning': return 'text-horus-status-warning'
    case 'success': return 'text-horus-status-success'
    default: return 'text-horus-accent-cyan'
  }
})

function handleInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', Number(target.value))
}
</script>

<template>
  <div class="space-y-2">
    <div v-if="label || showValue" class="flex items-center justify-between">
      <span v-if="label" class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
        {{ label }}
      </span>
      <span v-if="showValue" :class="['text-sm font-mono', valueColorClass]">
        {{ displayValue }}
      </span>
    </div>
    
    <div class="relative">
      <!-- Track background -->
      <div class="w-full h-1.5 bg-horus-bg-secondary rounded-full overflow-hidden">
        <!-- Fill -->
        <div
          :class="['h-full rounded-full transition-all duration-150', fillColorClass]"
          :style="{ width: `${percentage}%` }"
        />
      </div>
      
      <!-- Native range input (invisible but functional) -->
      <input
        type="range"
        :value="modelValue"
        :min="min"
        :max="max"
        :step="step"
        class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        @input="handleInput"
      />
    </div>
  </div>
</template>
