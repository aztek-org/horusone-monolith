<script setup lang="ts">
interface Option {
  value: string | number
  label: string
}

interface Props {
  modelValue: string | number
  options: Option[]
  label?: string
  placeholder?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Select an option',
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

function handleChange(event: Event) {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="space-y-1.5">
    <label v-if="label" class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
      {{ label }}
    </label>
    
    <div class="relative">
      <select
        :value="modelValue"
        :disabled="disabled"
        class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 pr-10 text-sm text-horus-text-primary appearance-none cursor-pointer focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        @change="handleChange"
      >
        <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      
      <div class="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
        <Icon name="heroicons:chevron-down-20-solid" class="w-5 h-5 text-horus-text-muted" />
      </div>
    </div>
  </div>
</template>
