<script setup lang="ts">
import type { ValidationResult } from '~/composables/useFlightPlans'

interface Props {
  results: readonly ValidationResult[]
  isLoading: boolean
}

const props = defineProps<Props>()

const passCount = computed(() =>
  props.results.filter(r => r.status === 'pass').length,
)
const warnCount = computed(() =>
  props.results.filter(r => r.status === 'warning').length,
)
const failCount = computed(() =>
  props.results.filter(r => r.status === 'fail').length,
)

function statusIcon(status: ValidationResult['status']): string {
  switch (status) {
    case 'pass': return 'heroicons:check-circle-solid'
    case 'warning': return 'heroicons:exclamation-triangle-solid'
    case 'fail': return 'heroicons:x-circle-solid'
    default: return 'heroicons:question-mark-circle'
  }
}

function statusColor(status: ValidationResult['status']): string {
  switch (status) {
    case 'pass': return 'text-horus-status-success'
    case 'warning': return 'text-horus-status-warning'
    case 'fail': return 'text-horus-status-danger'
    default: return 'text-horus-text-muted'
  }
}

function statusBgColor(status: ValidationResult['status']): string {
  switch (status) {
    case 'pass': return 'bg-horus-status-success/5 border-horus-status-success/20'
    case 'warning': return 'bg-horus-status-warning/5 border-horus-status-warning/20'
    case 'fail': return 'bg-horus-status-danger/5 border-horus-status-danger/20'
    default: return 'bg-horus-bg-tertiary border-horus-border-subtle'
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon
          name="heroicons:clipboard-document-check"
          class="w-5 h-5 text-horus-accent-cyan"
        />
        <h3 class="text-sm font-semibold text-horus-text-primary uppercase tracking-wider">
          Validation Results
        </h3>
      </div>

      <!-- Loading spinner -->
      <Icon
        v-if="isLoading"
        name="svg-spinners:ring-resize"
        class="w-5 h-5 text-horus-accent-cyan"
      />
    </div>

    <!-- Loading State -->
    <div
      v-if="isLoading"
      class="flex items-center justify-center py-8"
    >
      <div class="text-center space-y-2">
        <Icon
          name="svg-spinners:ring-resize"
          class="w-6 h-6 text-horus-accent-cyan mx-auto"
        />
        <p class="text-xs text-horus-text-muted">
          Running validation checks...
        </p>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="results.length === 0"
      class="text-center py-6"
    >
      <Icon
        name="heroicons:clipboard-document"
        class="w-8 h-8 text-horus-text-muted mx-auto mb-2 opacity-50"
      />
      <p class="text-xs text-horus-text-muted">
        No validation results yet
      </p>
      <p class="text-xxs text-horus-text-muted mt-1">
        Click "Validate" to run checks
      </p>
    </div>

    <template v-else>
      <!-- Summary Bar -->
      <div class="flex items-center gap-4 p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle">
        <div class="flex items-center gap-1.5">
          <Icon
            name="heroicons:check-circle-solid"
            class="w-4 h-4 text-horus-status-success"
          />
          <span class="text-xs font-mono text-horus-status-success">{{ passCount }}</span>
          <span class="text-xxs text-horus-text-muted">passed</span>
        </div>
        <div class="flex items-center gap-1.5">
          <Icon
            name="heroicons:exclamation-triangle-solid"
            class="w-4 h-4 text-horus-status-warning"
          />
          <span class="text-xs font-mono text-horus-status-warning">{{ warnCount }}</span>
          <span class="text-xxs text-horus-text-muted">warnings</span>
        </div>
        <div class="flex items-center gap-1.5">
          <Icon
            name="heroicons:x-circle-solid"
            class="w-4 h-4 text-horus-status-danger"
          />
          <span class="text-xs font-mono text-horus-status-danger">{{ failCount }}</span>
          <span class="text-xxs text-horus-text-muted">errors</span>
        </div>
      </div>

      <!-- Results List -->
      <div class="space-y-2">
        <div
          v-for="result in results"
          :key="`${result.agent}-${result.check_name}`"
          :class="[
            'flex items-start gap-3 p-3 rounded-lg border transition-colors',
            statusBgColor(result.status),
          ]"
        >
          <Icon
            :name="statusIcon(result.status)"
            :class="['w-5 h-5 flex-shrink-0 mt-0.5', statusColor(result.status)]"
          />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-sm font-medium text-horus-text-primary">
                {{ result.check_name }}
              </span>
              <HBadge
                variant="default"
                size="sm"
              >
                {{ result.agent }}
              </HBadge>
            </div>
            <p class="text-xs text-horus-text-secondary">
              {{ result.message }}
            </p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
