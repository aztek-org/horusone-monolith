<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: 'auth',
})

interface TrainingSession {
  id: number
  client_id: string | null
  scenario_id: number | null
  language: string
  status: string
  started_at: string
  ended_at: string | null
}

interface SessionCompletionResponse {
  session_id: number
  status: string
  ended_at: string | null
  already_completed: boolean
  scoring: unknown | null
  badges_earned: string[]
  report: string
  replay_path: string
}

const route = useRoute()
const router = useRouter()
const api = useApi()

const sessionId = computed(() => route.params.id as string)

const session = ref<TrainingSession | null>(null)
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const isCompleting = ref(false)
const completionError = ref<string | null>(null)

async function fetchSession() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const loadedSession = await api.get<TrainingSession>(`/api/v1/sessions/${sessionId.value}`)
    session.value = loadedSession

    if (loadedSession.status === 'completed') {
      await router.replace(`/session/${loadedSession.id}`)
      return
    }
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load session'
  }
  finally {
    isLoading.value = false
  }
}

async function completeSession() {
  if (!session.value || isCompleting.value) return
  if (!window.confirm('End this mission and open replay now?')) return

  isCompleting.value = true
  completionError.value = null
  try {
    const response = await api.post<SessionCompletionResponse>(
      `/api/v1/sessions/${sessionId.value}/complete`,
    )

    session.value.status = response.status
    session.value.ended_at = response.ended_at

    await router.push(response.replay_path || `/session/${sessionId.value}`)
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    completionError.value = apiErr.detail ?? 'Failed to complete session'
  }
  finally {
    isCompleting.value = false
  }
}

// Provide the authenticated WebSocket URL to child components
const authenticatedWsUrl = ref<string | null>(null)

async function initWebSocket() {
  try {
    authenticatedWsUrl.value = await api.getAuthenticatedWsUrl()
  }
  catch {
    console.error('Failed to get authenticated WebSocket URL')
  }
}

provide('sessionData', session)
provide('authenticatedWsUrl', authenticatedWsUrl)

onMounted(async () => {
  await fetchSession()
  if (session.value?.status === 'active') {
    await initWebSocket()
  }
})
</script>

<template>
  <NuxtLayout name="mission">
    <template #sidebar>
      <!-- Loading State -->
      <div v-if="isLoading" class="flex items-center justify-center py-8">
        <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
      </div>

      <!-- Error State -->
      <div
        v-else-if="errorMessage"
        class="p-4 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
      >
        <div class="flex items-center gap-2 mb-2">
          <Icon name="heroicons:exclamation-triangle" class="w-5 h-5 text-horus-status-danger" />
          <span class="text-sm text-horus-status-danger">{{ errorMessage }}</span>
        </div>
        <HButton variant="ghost" size="sm" @click="fetchSession">
          <Icon name="heroicons:arrow-path" class="w-4 h-4" />
          Retry
        </HButton>
      </div>

      <!-- Session Loaded -->
      <div v-else class="space-y-6">
        <!-- Session Info -->
        <div v-if="session" class="space-y-2 p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle">
          <div class="flex items-center justify-between">
            <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Session</span>
            <HBadge :variant="session.status === 'active' ? 'active' : 'idle'" size="sm">
              {{ session.status }}
            </HBadge>
          </div>
          <p class="text-sm font-mono text-horus-text-primary">#{{ session.id }}</p>
          <p v-if="session.scenario_id" class="text-xxs text-horus-text-muted">
            Scenario ID: {{ session.scenario_id }}
          </p>
        </div>

        <div v-if="session?.status === 'active'" class="space-y-2">
          <HButton
            variant="danger"
            size="sm"
            class="w-full"
            icon="heroicons:check-circle"
            :loading="isCompleting"
            @click="completeSession"
          >
            End Mission & Open Replay
          </HButton>
          <p class="text-xxs text-horus-text-muted">
            This finalizes the session and redirects to replay analysis.
          </p>
        </div>

        <div
          v-if="completionError"
          class="p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
        >
          <div class="flex items-center gap-2">
            <Icon name="heroicons:exclamation-triangle" class="w-4 h-4 text-horus-status-danger" />
            <span class="text-xs text-horus-status-danger">{{ completionError }}</span>
          </div>
        </div>

        <MissionChecklist />
        <SystemStatusGrid />
      </div>
    </template>

    <template #default>
      <!-- Loading State -->
      <div v-if="isLoading" class="flex items-center justify-center py-16">
        <div class="text-center space-y-3">
          <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
          <p class="text-sm text-horus-text-muted">Loading mission data...</p>
        </div>
      </div>

      <div v-else class="space-y-4">
        <!-- Weather & Decision Matrix Row -->
        <div class="grid gap-4 lg:grid-cols-2">
          <WeatherEcosystem />
          <div class="space-y-4">
            <DecisionMatrix />
            <FlightDynamics />
          </div>
        </div>
      </div>
    </template>

    <template #panel>
      <TrainingInterface />
    </template>
  </NuxtLayout>
</template>
