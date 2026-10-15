<script setup lang="ts">
const { state: simulation, pauseSimulation, resumeSimulation } = useSimulationState()
const { params: aiParams, interventionModes, setInterventionMode } = useAICopilot()
const { entries: commsLog } = useCommsLog()

const decisionScore = ref(88)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-2">
      <Icon
        name="heroicons:academic-cap"
        class="w-5 h-5 text-horus-accent-cyan"
      />
      <h2 class="text-sm font-semibold text-horus-text-primary">
        TRAINING INTERFACE
      </h2>
    </div>

    <!-- Simulation State -->
    <div class="space-y-3">
      <span class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
        SIMULATION STATE
      </span>
      <div class="flex gap-2">
        <HButton
          :variant="simulation.status === 'running' ? 'success' : 'secondary'"
          size="sm"
          class="flex-1"
          @click="resumeSimulation"
        >
          RESUME
        </HButton>
        <HButton
          variant="secondary"
          size="sm"
          class="flex-1"
          @click="pauseSimulation"
        >
          <Icon
            name="heroicons:pause"
            class="w-4 h-4 mr-1"
          />
          FREEZE
        </HButton>
      </div>
    </div>

    <!-- AI Intervention -->
    <div class="space-y-3">
      <span class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
        AI INTERVENTION
      </span>
      <HRadioGroup
        :model-value="aiParams.interventionMode"
        :options="interventionModes"
        name="intervention"
        @update:model-value="setInterventionMode($event as 'monitor' | 'assistance' | 'override')"
      />
    </div>

    <!-- Comms Log -->
    <div class="space-y-3">
      <span class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
        COMMS LOG
      </span>
      <div class="max-h-40 overflow-y-auto space-y-2 p-3 rounded-lg bg-horus-bg-secondary/50 border border-horus-border-subtle scrollbar-hide">
        <HLogEntry
          v-for="entry in commsLog"
          :key="entry.id"
          :timestamp="entry.timestamp"
          :type="entry.type"
          :variant="entry.variant"
        >
          {{ entry.message }}
        </HLogEntry>
      </div>
    </div>

    <!-- Decision Score -->
    <div class="space-y-2 pt-4 border-t border-horus-border-subtle">
      <div class="flex items-center justify-between">
        <span class="text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
          DECISION SCORE
        </span>
        <span class="text-sm font-mono text-horus-accent-cyan">{{ decisionScore }}/100</span>
      </div>
      <HProgress
        :value="decisionScore"
        :show-percentage="false"
        variant="success"
      />
    </div>

    <!-- Export Button -->
    <HButton
      variant="secondary"
      class="w-full"
      icon="heroicons:arrow-down-tray"
    >
      EXPORT MISSION REPORT
    </HButton>
  </div>
</template>
