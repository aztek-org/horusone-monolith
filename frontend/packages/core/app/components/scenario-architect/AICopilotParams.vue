<script setup lang="ts">
const {
  params,
  commsStyleOptions,
  knowledgeLevels,
  setAssertiveness,
  setErrorRate,
  setKnowledgeLevel,
  setCommsStyle,
} = useAICopilot()

const localAssertiveness = ref(params.value.assertiveness)
const localErrorRate = ref(params.value.simulatedErrorRate)

// Sync local values with composable
watch(localAssertiveness, val => setAssertiveness(val))
watch(localErrorRate, val => setErrorRate(val))
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon
          name="heroicons:cpu-chip"
          class="w-5 h-5 text-horus-accent-cyan"
        />
        <h2 class="text-sm font-semibold text-horus-text-primary">
          AI COPILOT PARAMETERS
        </h2>
      </div>
      <span class="text-xs text-horus-accent-cyan">Expert</span>
    </div>

    <p class="text-xs text-horus-text-muted">
      Configure persona behavioral thresholds
    </p>

    <!-- Assertiveness Slider -->
    <div class="space-y-2">
      <HSlider
        v-model="localAssertiveness"
        :min="0"
        :max="100"
        label="ASSERTIVENESS"
        variant="default"
      />
      <p class="text-xxs text-horus-text-muted italic">
        Higher values lead to the AI challenging pilot decisions more frequently during anomalies.
      </p>
    </div>

    <!-- Simulated Error Rate -->
    <div class="space-y-2">
      <HSlider
        v-model="localErrorRate"
        :min="0"
        :max="50"
        :step="0.5"
        label="SIMULATED ERROR RATE"
        variant="danger"
        :value-format="(v: number) => `${v.toFixed(1)}%`"
      />
      <p class="text-xxs text-horus-text-muted italic">
        Determines the frequency of human-like procedural errors for the pilot to identify and correct.
      </p>
    </div>

    <!-- Procedural Knowledge -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
          PROCEDURAL KNOWLEDGE
        </span>
        <span class="text-xs text-horus-accent-cyan">{{ params.proceduralKnowledge }}</span>
      </div>

      <div class="flex gap-2">
        <button
          v-for="level in knowledgeLevels"
          :key="level.value"
          :class="[
            'flex-1 px-3 py-2 rounded-md text-xs font-medium transition-all',
            params.proceduralKnowledge === level.value
              ? 'bg-horus-accent-cyan text-horus-bg-primary'
              : 'bg-horus-bg-secondary text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary border border-horus-border-subtle',
          ]"
          @click="setKnowledgeLevel(level.value as 'novice' | 'proficient' | 'expert')"
        >
          {{ level.label.toUpperCase() }}
        </button>
      </div>
    </div>

    <!-- Comms Style -->
    <div class="space-y-3">
      <span class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
        COMMS STYLE
      </span>

      <HDropdown
        :model-value="params.commsStyle"
        :options="commsStyleOptions"
        @update:model-value="(val: string | number) => setCommsStyle(String(val))"
      />
    </div>

    <!-- Export Button -->
    <div class="pt-4 border-t border-horus-border-subtle">
      <HButton
        variant="secondary"
        class="w-full"
        icon="heroicons:arrow-down-tray"
      >
        EXPORT SCENARIO PROFILE
      </HButton>
    </div>
  </div>
</template>
