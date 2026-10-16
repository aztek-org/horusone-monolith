<script setup lang="ts">
const { params: aiParams } = useAICopilot()
const { weather } = useWeatherData()

const emit = defineEmits<{
  accept: []
  requestAlt: []
}>()

const proposedAction = computed(() => ({
  summary: weather.value.analysis || 'Analyzing current conditions...',
  action: 'Divert immediately to KTEB. Estimated fuel remaining at landing: 4,200 lbs.',
  confidence: aiParams.value.confidence,
}))
</script>

<template>
  <HCard
    variant="elevated"
    padding="md"
    class="space-y-4"
  >
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon
          name="heroicons:cpu-chip"
          class="w-5 h-5 text-horus-accent-cyan"
        />
        <h3 class="text-sm font-semibold text-horus-text-primary">
          AI COPILOT DECISION MATRIX
        </h3>
      </div>
      <HBadge
        variant="active"
        size="sm"
      >
        HIGH CONFIDENCE ({{ proposedAction.confidence }}%)
      </HBadge>
    </div>

    <div class="flex flex-col lg:flex-row gap-4">
      <!-- Analysis -->
      <div class="flex-1 space-y-3">
        <div class="text-xxs text-horus-text-muted uppercase">
          Current Analysis:
        </div>
        <div class="p-4 rounded-lg bg-horus-bg-secondary/50 border border-horus-border-subtle">
          <p class="text-sm text-horus-text-secondary leading-relaxed">
            "{{ proposedAction.summary }}
            <span class="text-horus-status-warning font-semibold">PROPOSED ACTION:</span>
            {{ proposedAction.action }}"
          </p>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex flex-row lg:flex-col gap-2 lg:w-44">
        <HButton
          variant="success"
          class="flex-1"
          icon="heroicons:check"
          @click="emit('accept')"
        >
          ACCEPT PROPOSAL
        </HButton>
        <HButton
          variant="secondary"
          class="flex-1"
          @click="emit('requestAlt')"
        >
          REQUEST ALT OPTION
        </HButton>
      </div>
    </div>
  </HCard>
</template>
