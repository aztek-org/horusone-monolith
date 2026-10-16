<script setup lang="ts">
interface Props {
  status: 'pending' | 'in-progress' | 'completed' | 'warning' | 'error'
  title: string
  subtitle?: string
  meta?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  click: []
}>()

const statusConfig = {
  'pending': {
    icon: 'heroicons:ellipsis-horizontal-circle',
    iconClass: 'text-horus-text-muted',
    ringClass: 'border-horus-border-default',
  },
  'in-progress': {
    icon: 'svg-spinners:ring-resize',
    iconClass: 'text-horus-accent-cyan',
    ringClass: 'border-horus-accent-cyan',
  },
  'completed': {
    icon: 'heroicons:check-circle-solid',
    iconClass: 'text-horus-status-success',
    ringClass: 'border-horus-status-success',
  },
  'warning': {
    icon: 'heroicons:exclamation-triangle-solid',
    iconClass: 'text-horus-status-warning',
    ringClass: 'border-horus-status-warning',
  },
  'error': {
    icon: 'heroicons:x-circle-solid',
    iconClass: 'text-horus-status-danger',
    ringClass: 'border-horus-status-danger',
  },
}

const config = computed(() => statusConfig[props.status])
</script>

<template>
  <button
    :class="[
      'flex items-start gap-3 w-full p-3 rounded-lg text-left transition-all duration-200',
      'hover:bg-horus-bg-tertiary/50',
      disabled && 'opacity-50 cursor-not-allowed',
      status === 'completed' && 'opacity-75',
    ]"
    :disabled="disabled"
    @click="emit('click')"
  >
    <div
      :class="[
        'flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center',
        config.ringClass,
      ]"
    >
      <Icon
        :name="config.icon"
        :class="['w-4 h-4', config.iconClass]"
      />
    </div>

    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span
          :class="[
            'text-sm font-medium',
            status === 'completed' ? 'text-horus-text-secondary line-through' : 'text-horus-text-primary',
          ]"
        >
          {{ title }}
        </span>
        <span
          v-if="meta"
          class="text-xxs font-mono text-horus-text-muted"
        >
          {{ meta }}
        </span>
      </div>
      <p
        v-if="subtitle"
        class="text-xs text-horus-text-muted mt-0.5 truncate"
      >
        {{ subtitle }}
      </p>
    </div>
  </button>
</template>
