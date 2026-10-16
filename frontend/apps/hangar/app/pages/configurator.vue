<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: 'auth',
})

interface Scenario {
  id: number
  name: string
  description: string | null
  difficulty: number
  airport_icao: string
  runway: string
  weather_preset: string
  phase: string
  created_at: string
}

const { startSimulation } = useSimulationState()
const { hasActiveSeat, hasAnyRole } = useAuth()
const router = useRouter()
const api = useApi()

const scenarios = ref<Scenario[]>([])
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const isCreating = ref(false)
const canTrain = computed(() => hasActiveSeat.value || hasAnyRole('platform-admin'))

async function fetchScenarios() {
  isLoading.value = true
  errorMessage.value = null
  try {
    scenarios.value = await api.get<Scenario[]>('/api/v1/scenarios')
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load scenarios'
  }
  finally {
    isLoading.value = false
  }
}

async function handleExecuteSimulation() {
  if (scenarios.value.length === 0) return
  if (!canTrain.value) {
    errorMessage.value = 'You need an active seat to start a training session. Contact your organization admin.'
    return
  }

  isCreating.value = true
  errorMessage.value = null
  try {
    // Create a new training session for the first scenario
    const scenario = scenarios.value[0]
    if (!scenario) {
      errorMessage.value = 'No scenarios available to start a session.'
      return
    }
    const session = await api.post<{ id: number }>('/api/v1/sessions', {
      scenario_id: scenario.id,
      language: 'en',
    })

    const missionId = String(session.id)
    startSimulation(missionId, `${scenario.airport_icao}-${scenario.runway}`)
    router.push(`/mission/${missionId}`)
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to create simulation session'
  }
  finally {
    isCreating.value = false
  }
}

onMounted(() => {
  fetchScenarios()
})
</script>

<template>
  <NuxtLayout name="default">
    <template #header>
      <AppHeader title="Route & Scenario Architect" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO">
        <template #action>
          <HButton
            variant="primary"
            size="sm"
            icon="heroicons:play-solid"
            :loading="isCreating"
            :disabled="isLoading || scenarios.length === 0 || !canTrain"
            :title="!canTrain ? 'Requires an active seat' : ''"
            @click="handleExecuteSimulation"
          >
            EXECUTE SIMULATION
          </HButton>
        </template>
      </AppHeader>
    </template>

    <template #sidebar>
      <RouteChecklist />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-4">
        <!-- Error Banner -->
        <div
          v-if="errorMessage"
          class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
        >
          <Icon name="heroicons:exclamation-triangle" class="w-5 h-5 text-horus-status-danger flex-shrink-0" />
          <span class="text-sm text-horus-status-danger">{{ errorMessage }}</span>
          <button
            class="ml-auto text-horus-status-danger hover:text-horus-text-primary"
            @click="errorMessage = null"
          >
            <Icon name="heroicons:x-mark" class="w-4 h-4" />
          </button>
        </div>

        <!-- Seat Warning -->
        <div
          v-if="!canTrain"
          class="flex items-start gap-3 p-4 rounded-lg bg-horus-status-warning/10 border border-horus-status-warning/30"
        >
          <Icon name="heroicons:exclamation-circle" class="w-6 h-6 text-horus-status-warning flex-shrink-0 mt-0.5" />
          <div>
            <p class="text-sm font-medium text-horus-status-warning">Read-Only Mode</p>
            <p class="text-xs text-horus-text-secondary mt-1">
              You don't have an active seat. You can browse scenarios but cannot start training sessions.
            </p>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-16">
          <div class="text-center space-y-3">
            <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
            <p class="text-sm text-horus-text-muted">Loading scenarios...</p>
          </div>
        </div>

        <template v-else>
          <!-- Chart Layers -->
          <ChartLayers />

          <!-- Map Visualization -->
          <MapVisualization />
        </template>
      </div>
    </template>

    <template #panel>
      <AICopilotParams />
    </template>
  </NuxtLayout>
</template>
