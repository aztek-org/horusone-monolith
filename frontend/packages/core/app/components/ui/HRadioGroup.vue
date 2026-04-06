<script setup lang="ts">
interface Props {
  modelValue: string
  options: { value: string; label: string }[]
  name: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="space-y-2">
    <button
      v-for="option in options"
      :key="option.value"
      :class="[
        'w-full flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-all duration-200',
        modelValue === option.value
          ? 'bg-horus-accent-cyan/10 border-horus-accent-cyan text-horus-text-primary'
          : 'bg-horus-bg-secondary/50 border-horus-border-subtle text-horus-text-secondary hover:border-horus-accent-cyan/30 hover:bg-horus-bg-tertiary/50'
      ]"
      @click="emit('update:modelValue', option.value)"
    >
      <div
        :class="[
          'w-4 h-4 rounded-full border-2 flex items-center justify-center transition-all',
          modelValue === option.value
            ? 'border-horus-accent-cyan'
            : 'border-horus-border-default'
        ]"
      >
        <div
          v-if="modelValue === option.value"
          class="w-2 h-2 rounded-full bg-horus-accent-cyan"
        />
      </div>
      <span class="text-sm font-medium">{{ option.label }}</span>
    </button>
  </div>
</template>
