<script setup lang="ts">
definePageMeta({
  layout: 'default',
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

interface TrainingSession {
  id: number
  client_id: string | null
  scenario_id: number | null
  language: string
  status: string
  started_at: string
  ended_at: string | null
}

const { user, hasRole, hasAnyRole, hasActiveSeat, activeSeat } = useAuth()
const api = useApi()
const router = useRouter()

const isOrgUser = computed(() => hasAnyRole('org-admin', 'instructor'))
const orgId = computed(() => user.value?.organizationId)

const scenarios = ref<Scenario[]>([])
const sessions = ref<TrainingSession[]>([])
const isLoadingScenarios = ref(true)
const isLoadingSessions = ref(true)
const errorMessage = ref<string | null>(null)

async function fetchScenarios() {
  isLoadingScenarios.value = true
  try {
    scenarios.value = await api.get<Scenario[]>('/api/v1/scenarios')
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load scenarios'
  }
  finally {
    isLoadingScenarios.value = false
  }
}

async function fetchSessions() {
  isLoadingSessions.value = true
  try {
    sessions.value = await api.get<TrainingSession[]>('/api/v1/sessions')
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load sessions'
  }
  finally {
    isLoadingSessions.value = false
  }
}

const activeSessions = computed(() =>
  sessions.value.filter(s => s.status === 'active'),
)

const completedSessions = computed(() =>
  sessions.value.filter(s => s.status === 'completed'),
)

const recentSessions = computed(() =>
  [...sessions.value]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 6),
)

function getDifficultyLabel(level: number): string {
  if (level >= 4) return 'Expert'
  if (level >= 2) return 'Proficient'
  return 'Novice'
}

function getDifficultyVariant(level: number): 'danger' | 'warning' | 'active' {
  if (level >= 4) return 'danger'
  if (level >= 2) return 'warning'
  return 'active'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(session: TrainingSession): string {
  if (!session.ended_at) return 'In progress'
  const start = new Date(session.started_at).getTime()
  const end = new Date(session.ended_at).getTime()
  const mins = Math.round((end - start) / 60000)
  return `${mins} min`
}

function navigateToSession(id: number) {
  router.push(`/mission/${id}`)
}

onMounted(() => {
  fetchScenarios()
  fetchSessions()
})
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader title="Organization Dashboard" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO" />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <!-- Page Title & Role Badge -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 class="text-xl font-semibold text-horus-text-primary">
              Welcome, {{ user?.displayName ?? 'Pilot' }}
            </h1>
            <p class="text-sm text-horus-text-secondary mt-1">
              Organization training overview and management
            </p>
          </div>
          <div class="flex items-center gap-2">
            <HBadge v-if="hasRole('org-admin')" variant="cyan" size="sm">
              ORG ADMIN
            </HBadge>
            <HBadge v-else-if="hasRole('instructor')" variant="info" size="sm">
              INSTRUCTOR
            </HBadge>
            <HBadge v-else variant="active" size="sm">
              STUDENT
            </HBadge>
          </div>
        </div>

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

        <!-- No Active Seat Banner -->
        <div
          v-if="!hasActiveSeat && !hasAnyRole('platform-admin')"
          class="flex items-start gap-3 p-4 rounded-lg bg-horus-status-warning/10 border border-horus-status-warning/30"
        >
          <Icon name="heroicons:exclamation-circle" class="w-6 h-6 text-horus-status-warning flex-shrink-0 mt-0.5" />
          <div>
            <p class="text-sm font-medium text-horus-status-warning">No Active Seat</p>
            <p class="text-xs text-horus-text-secondary mt-1">
              You don't have an active seat in any organization. You can browse scenarios and view
              stats, but you cannot start training sessions or use the voice communication system.
              Contact your organization administrator to request a seat.
            </p>
          </div>
        </div>

        <!-- Stats Overview -->
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <HCard variant="default" padding="md">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-accent-cyan/10 flex items-center justify-center">
                <Icon name="heroicons:book-open" class="w-5 h-5 text-horus-accent-cyan" />
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Scenarios</p>
                <p class="text-xl font-bold text-horus-text-primary font-mono">
                  <template v-if="isLoadingScenarios">—</template>
                  <template v-else>{{ scenarios.length }}</template>
                </p>
              </div>
            </div>
          </HCard>

          <HCard variant="default" padding="md">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-status-success/10 flex items-center justify-center">
                <Icon name="heroicons:play-circle" class="w-5 h-5 text-horus-status-success" />
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Active Sessions</p>
                <p class="text-xl font-bold text-horus-text-primary font-mono">
                  <template v-if="isLoadingSessions">—</template>
                  <template v-else>{{ activeSessions.length }}</template>
                </p>
              </div>
            </div>
          </HCard>

          <HCard variant="default" padding="md">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-status-warning/10 flex items-center justify-center">
                <Icon name="heroicons:check-circle" class="w-5 h-5 text-horus-status-warning" />
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Completed</p>
                <p class="text-xl font-bold text-horus-text-primary font-mono">
                  <template v-if="isLoadingSessions">—</template>
                  <template v-else>{{ completedSessions.length }}</template>
                </p>
              </div>
            </div>
          </HCard>

          <HCard variant="default" padding="md">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-horus-status-info/10 flex items-center justify-center">
                <Icon name="heroicons:signal" class="w-5 h-5 text-horus-status-info" />
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Total Sessions</p>
                <p class="text-xl font-bold text-horus-text-primary font-mono">
                  <template v-if="isLoadingSessions">—</template>
                  <template v-else>{{ sessions.length }}</template>
                </p>
              </div>
            </div>
          </HCard>
        </div>

        <!-- Active Training Sessions (Instructor/Admin only) -->
        <HSection
          v-if="isOrgUser"
          icon="heroicons:play-circle"
          title="Active Training Sessions"
        >
          <div v-if="isLoadingSessions" class="flex items-center justify-center py-8">
            <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
          </div>

          <div
            v-else-if="activeSessions.length === 0"
            class="text-center py-8"
          >
            <Icon name="heroicons:play-circle" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
            <p class="text-sm text-horus-text-muted">No active training sessions</p>
          </div>

          <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <HCard
              v-for="session in activeSessions"
              :key="session.id"
              variant="default"
              padding="md"
              hover
              class="cursor-pointer"
              @click="navigateToSession(session.id)"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-semibold text-horus-text-primary font-mono">
                  Session #{{ session.id }}
                </span>
                <HStatusPill :online="true" label="LIVE" variant="success" />
              </div>
              <div class="space-y-1 text-xs text-horus-text-muted">
                <p v-if="session.scenario_id">Scenario ID: {{ session.scenario_id }}</p>
                <p>Started: {{ formatDate(session.started_at) }}</p>
                <p>Language: {{ session.language.toUpperCase() }}</p>
              </div>
            </HCard>
          </div>
        </HSection>

        <!-- Recent Sessions -->
        <HSection icon="heroicons:clock" title="Recent Sessions">
          <div v-if="isLoadingSessions" class="flex items-center justify-center py-8">
            <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
          </div>

          <div
            v-else-if="recentSessions.length === 0"
            class="text-center py-8"
          >
            <Icon name="heroicons:clock" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
            <p class="text-sm text-horus-text-muted">No training sessions recorded yet</p>
            <HButton
              variant="primary"
              size="sm"
              icon="heroicons:play"
              class="mt-3"
              :disabled="!hasActiveSeat && !hasAnyRole('platform-admin')"
              :title="!hasActiveSeat && !hasAnyRole('platform-admin') ? 'Requires an active seat' : ''"
              @click="router.push('/configurator')"
            >
              Start First Session
            </HButton>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-xxs text-horus-text-muted uppercase tracking-wider border-b border-horus-border-subtle">
                  <th class="pb-2 pr-4">ID</th>
                  <th class="pb-2 pr-4">Status</th>
                  <th class="pb-2 pr-4">Scenario</th>
                  <th class="pb-2 pr-4">Started</th>
                  <th class="pb-2 pr-4">Duration</th>
                  <th class="pb-2" />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="session in recentSessions"
                  :key="session.id"
                  class="border-b border-horus-border-subtle/50 hover:bg-horus-bg-tertiary/30 transition-colors cursor-pointer"
                  @click="navigateToSession(session.id)"
                >
                  <td class="py-3 pr-4 font-mono text-horus-text-primary">#{{ session.id }}</td>
                  <td class="py-3 pr-4">
                    <HBadge
                      :variant="session.status === 'active' ? 'active' : session.status === 'completed' ? 'idle' : 'warning'"
                      size="sm"
                    >
                      {{ session.status }}
                    </HBadge>
                  </td>
                  <td class="py-3 pr-4 text-horus-text-secondary">
                    {{ session.scenario_id ? `#${session.scenario_id}` : '—' }}
                  </td>
                  <td class="py-3 pr-4 text-horus-text-muted">{{ formatDate(session.started_at) }}</td>
                  <td class="py-3 pr-4 text-horus-text-muted font-mono">{{ formatDuration(session) }}</td>
                  <td class="py-3">
                    <Icon name="heroicons:chevron-right" class="w-4 h-4 text-horus-text-muted" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </HSection>

        <!-- Scenario Library -->
        <HSection icon="heroicons:book-open" title="Scenario Library">
          <div v-if="isLoadingScenarios" class="flex items-center justify-center py-8">
            <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
          </div>

          <div
            v-else-if="scenarios.length === 0"
            class="text-center py-8"
          >
            <Icon name="heroicons:book-open" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
            <p class="text-sm text-horus-text-muted">No scenarios available</p>
          </div>

          <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <HCard
              v-for="scenario in scenarios.slice(0, 6)"
              :key="scenario.id"
              variant="default"
              padding="md"
              hover
            >
              <div class="space-y-2">
                <div class="flex items-start justify-between">
                  <h4 class="text-sm font-semibold text-horus-text-primary">{{ scenario.name }}</h4>
                  <HBadge :variant="getDifficultyVariant(scenario.difficulty)" size="sm">
                    {{ getDifficultyLabel(scenario.difficulty) }}
                  </HBadge>
                </div>
                <p v-if="scenario.description" class="text-xs text-horus-text-secondary line-clamp-2">
                  {{ scenario.description }}
                </p>
                <div class="flex items-center gap-3 text-xxs text-horus-text-muted">
                  <span class="flex items-center gap-1">
                    <Icon name="heroicons:map-pin" class="w-3 h-3" />
                    {{ scenario.airport_icao }}
                  </span>
                  <span class="flex items-center gap-1">
                    <Icon name="heroicons:cloud" class="w-3 h-3" />
                    {{ scenario.weather_preset }}
                  </span>
                </div>
              </div>
            </HCard>
          </div>

          <div v-if="scenarios.length > 6" class="mt-4 text-center">
            <HButton variant="ghost" size="sm" @click="router.push('/library')">
              View all {{ scenarios.length }} scenarios
              <Icon name="heroicons:arrow-right" class="w-4 h-4" />
            </HButton>
          </div>
        </HSection>
      </div>
    </template>

    <template #panel>
      <div class="space-y-6">
        <!-- Organization Info -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:building-office-2" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">ORGANIZATION</h2>
          </div>

          <HCard variant="glass" padding="md">
            <div class="space-y-2">
              <p class="text-sm font-semibold text-horus-text-primary">
                {{ user?.displayName ?? 'Pilot' }}
              </p>
              <p class="text-xxs text-horus-text-muted">{{ user?.email }}</p>
              <div v-if="orgId" class="pt-2 border-t border-horus-border-subtle">
                <p class="text-xxs text-horus-text-muted">Org ID: {{ orgId }}</p>
              </div>
            </div>
          </HCard>
        </div>

        <!-- Quick Actions -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:bolt" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">QUICK ACTIONS</h2>
          </div>

          <div class="space-y-2">
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:play"
              class="w-full justify-start"
              :disabled="!hasActiveSeat && !hasAnyRole('platform-admin')"
              :title="!hasActiveSeat && !hasAnyRole('platform-admin') ? 'Requires an active seat' : ''"
              @click="router.push('/configurator')"
            >
              New Simulation
            </HButton>
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:book-open"
              class="w-full justify-start"
              @click="router.push('/library')"
            >
              Browse Scenarios
            </HButton>
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:chart-bar"
              class="w-full justify-start"
              @click="router.push('/performance')"
            >
              View Performance
            </HButton>
          </div>
        </div>

        <!-- System Status -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:server-stack" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">SYSTEM STATUS</h2>
          </div>

          <div class="space-y-2">
            <HStatusPill :online="true" label="API Connected" variant="success" />
            <HStatusPill :online="true" label="Voice WS Ready" variant="success" />
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
