<script setup lang="ts">
interface Props {
  modelValue: boolean
  label?: string
  description?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function toggle() {
  if (!props.disabled) {
    emit('update:modelValue', !props.modelValue)
  }
}
</script>

<template>
  <label
    :class="[
      'flex items-start gap-3 cursor-pointer group',
      disabled && 'opacity-50 cursor-not-allowed',
    ]"
    @click.prevent="toggle"
  >
    <div
      :class="[
        'relative flex-shrink-0 w-5 h-5 rounded border-2 transition-all duration-200',
        modelValue
          ? 'bg-horus-accent-cyan border-horus-accent-cyan'
          : 'bg-transparent border-horus-border-default group-hover:border-horus-accent-cyan/50',
      ]"
    >
      <svg
        v-if="modelValue"
        class="absolute inset-0 w-full h-full text-horus-bg-primary p-0.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="3"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M5 13l4 4L19 7"
        />
      </svg>
    </div>

    <div
      v-if="label || description"
      class="flex-1 min-w-0"
    >
      <span
        v-if="label"
        class="text-sm text-horus-text-primary"
      >{{ label }}</span>
      <p
        v-if="description"
        class="text-xs text-horus-text-muted mt-0.5"
      >{{ description }}</p>
    </div>
  </label>
</template>
