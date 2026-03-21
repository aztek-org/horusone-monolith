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

const api = useApi()

const sessions = ref<TrainingSession[]>([])
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const timeRange = ref('week')

async function fetchSessions() {
  isLoading.value = true
  errorMessage.value = null
  try {
    sessions.value = await api.get<TrainingSession[]>('/api/v1/sessions')
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load sessions'
  }
  finally {
    isLoading.value = false
  }
}

const completedSessions = computed(() =>
  sessions.value.filter(s => s.status === 'completed'),
)

const activeSessions = computed(() =>
  sessions.value.filter(s => s.status === 'active'),
)

const overallScore = computed(() => {
  if (completedSessions.value.length === 0) return 0
  // Calculate a simple score based on completed sessions count
  return Math.min(100, Math.round(completedSessions.value.length * 15 + 40))
})

const metrics = computed(() => [
  {
    label: 'Sessions Completed',
    value: completedSessions.value.length,
    trend: completedSessions.value.length > 0 ? 'up' as const : 'stable' as const,
  },
  {
    label: 'Active Sessions',
    value: activeSessions.value.length,
    trend: activeSessions.value.length > 0 ? 'up' as const : 'stable' as const,
  },
  {
    label: 'Total Sessions',
    value: sessions.value.length,
    trend: sessions.value.length > 0 ? 'up' as const : 'stable' as const,
  },
  {
    label: 'Avg Duration',
    value: avgDurationMinutes.value,
    trend: 'stable' as const,
  },
])

const avgDurationMinutes = computed(() => {
  const finished = completedSessions.value.filter(s => s.ended_at)
  if (finished.length === 0) return 0
  const totalMs = finished.reduce((sum, s) => {
    const start = new Date(s.started_at).getTime()
    const end = new Date(s.ended_at!).getTime()
    return sum + (end - start)
  }, 0)
  return Math.round(totalMs / finished.length / 60000)
})

const recentSessions = computed(() =>
  [...sessions.value]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 5),
)

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function formatDuration(session: TrainingSession): string {
  if (!session.ended_at) return 'In progress'
  const start = new Date(session.started_at).getTime()
  const end = new Date(session.ended_at).getTime()
  const mins = Math.round((end - start) / 60000)
  return `${mins} min`
}

function getStatusVariant(status: string): 'active' | 'warning' | 'idle' {
  switch (status) {
    case 'active': return 'active'
    case 'completed': return 'idle'
    default: return 'warning'
  }
}

onMounted(() => {
  fetchSessions()
})
</script>

<template>
  <NuxtLayout>
    <template #sidebar>
      <div class="space-y-6">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:calendar-days" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">TIME RANGE</h2>
        </div>

        <HButtonGroup
          v-model="timeRange"
          :options="[
            { value: 'day', label: 'Day' },
            { value: 'week', label: 'Week' },
            { value: 'month', label: 'Month' }
          ]"
          size="sm"
        />

        <div class="pt-4 border-t border-horus-border-subtle space-y-4">
          <h3 class="text-xs font-semibold text-horus-text-secondary uppercase">Recent Sessions</h3>

          <!-- Loading State -->
          <div v-if="isLoading" class="flex items-center justify-center py-4">
            <Icon name="svg-spinners:ring-resize" class="w-5 h-5 text-horus-accent-cyan" />
          </div>

          <!-- Empty State -->
          <p v-else-if="recentSessions.length === 0" class="text-xs text-horus-text-muted text-center py-4">
            No sessions yet
          </p>

          <!-- Session List -->
          <div v-else class="space-y-2">
            <NuxtLink
              v-for="session in recentSessions"
              :key="session.id"
              :to="`/mission/${session.id}`"
              class="block p-3 rounded-lg bg-horus-bg-tertiary/50 hover:bg-horus-bg-tertiary transition-colors cursor-pointer"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm text-horus-text-primary truncate">
                  Session #{{ session.id }}
                </span>
                <HBadge :variant="getStatusVariant(session.status)" size="sm">
                  {{ session.status }}
                </HBadge>
              </div>
              <div class="flex items-center gap-2 text-xxs text-horus-text-muted">
                <span>{{ formatDate(session.started_at) }}</span>
                <span>•</span>
                <span>{{ formatDuration(session) }}</span>
              </div>
            </NuxtLink>
          </div>
        </div>
      </div>
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <h1 class="text-xl font-semibold text-horus-text-primary">Performance Analytics</h1>

        <!-- Error Banner -->
        <div
          v-if="errorMessage"
          class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
        >
          <Icon name="heroicons:exclamation-triangle" class="w-5 h-5 text-horus-status-danger flex-shrink-0" />
          <span class="text-sm text-horus-status-danger">{{ errorMessage }}</span>
          <button
            class="ml-auto text-horus-status-danger hover:text-horus-text-primary"
            @click="fetchSessions"
          >
            <Icon name="heroicons:arrow-path" class="w-4 h-4" />
          </button>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-16">
          <div class="text-center space-y-3">
            <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
            <p class="text-sm text-horus-text-muted">Loading performance data...</p>
          </div>
        </div>

        <template v-else>
          <!-- Overall Score -->
          <HCard variant="elevated" padding="lg">
            <div class="flex flex-col md:flex-row md:items-center gap-6">
              <div class="flex-shrink-0">
                <div class="relative w-32 h-32">
                  <svg class="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="8"
                      class="text-horus-bg-secondary"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="8"
                      stroke-linecap="round"
                      class="text-horus-accent-cyan"
                      :stroke-dasharray="`${overallScore * 2.83} 283`"
                    />
                  </svg>
                  <div class="absolute inset-0 flex items-center justify-center">
                    <span class="text-3xl font-bold text-horus-text-primary">{{ overallScore }}</span>
                  </div>
                </div>
              </div>
              <div class="flex-1">
                <h2 class="text-lg font-semibold text-horus-text-primary mb-2">Overall Performance Score</h2>
                <p class="text-sm text-horus-text-secondary">
                  <template v-if="sessions.length === 0">
                    No sessions recorded yet. Start a training session to begin tracking your performance.
                  </template>
                  <template v-else>
                    Based on {{ sessions.length }} training session{{ sessions.length === 1 ? '' : 's' }}.
                    {{ completedSessions.length }} completed, {{ activeSessions.length }} active.
                  </template>
                </p>
              </div>
            </div>
          </HCard>

          <!-- Metrics Grid -->
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <HCard v-for="metric in metrics" :key="metric.label" variant="default" padding="md">
              <div class="space-y-2">
                <span class="text-xxs text-horus-text-muted uppercase">{{ metric.label }}</span>
                <div class="flex items-end justify-between">
                  <span class="text-2xl font-bold text-horus-text-primary">
                    {{ metric.label === 'Avg Duration' ? `${metric.value}m` : metric.value }}
                  </span>
                  <Icon
                    :name="metric.trend === 'up' ? 'heroicons:arrow-trending-up' : metric.trend === 'down' ? 'heroicons:arrow-trending-down' : 'heroicons:minus'"
                    :class="[
                      'w-5 h-5',
                      metric.trend === 'up' && 'text-horus-status-success',
                      metric.trend === 'down' && 'text-horus-status-danger',
                      metric.trend === 'stable' && 'text-horus-text-muted'
                    ]"
                  />
                </div>
              </div>
            </HCard>
          </div>

          <!-- Chart Placeholder -->
          <HCard variant="glass" padding="lg">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-semibold text-horus-text-primary">Performance Trend</h3>
              <HButtonGroup
                model-value="score"
                :options="[
                  { value: 'score', label: 'Score' },
                  { value: 'time', label: 'Time' }
                ]"
                size="sm"
              />
            </div>
            <div class="h-64 flex items-center justify-center border border-dashed border-horus-border-subtle rounded-lg">
              <div class="text-center text-horus-text-muted">
                <Icon name="heroicons:chart-bar" class="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p class="text-sm">Chart visualization</p>
                <p class="text-xs">Coming soon</p>
              </div>
            </div>
          </HCard>
        </template>
      </div>
    </template>

    <template #panel>
      <div class="space-y-6">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:trophy" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">ACHIEVEMENTS</h2>
        </div>

        <div class="space-y-3">
          <div
            :class="[
              'flex items-center gap-3 p-3 rounded-lg',
              completedSessions.length >= 5
                ? 'bg-horus-status-success/10 border border-horus-status-success/30'
                : 'bg-horus-bg-tertiary/50 border border-horus-border-subtle opacity-50'
            ]"
          >
            <Icon
              name="heroicons:star-solid"
              :class="['w-8 h-8', completedSessions.length >= 5 ? 'text-horus-status-success' : 'text-horus-text-muted']"
            />
            <div>
              <p class="text-sm font-medium text-horus-text-primary">Session Veteran</p>
              <p class="text-xxs text-horus-text-muted">Complete 5 training sessions</p>
            </div>
          </div>

          <div
            :class="[
              'flex items-center gap-3 p-3 rounded-lg',
              completedSessions.length >= 1
                ? 'bg-horus-accent-cyan/10 border border-horus-accent-cyan/30'
                : 'bg-horus-bg-tertiary/50 border border-horus-border-subtle opacity-50'
            ]"
          >
            <Icon
              name="heroicons:bolt-solid"
              :class="['w-8 h-8', completedSessions.length >= 1 ? 'text-horus-accent-cyan' : 'text-horus-text-muted']"
            />
            <div>
              <p class="text-sm font-medium text-horus-text-primary">First Flight</p>
              <p class="text-xxs text-horus-text-muted">Complete your first session</p>
            </div>
          </div>

          <div class="flex items-center gap-3 p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle opacity-50">
            <Icon name="heroicons:fire" class="w-8 h-8 text-horus-text-muted" />
            <div>
              <p class="text-sm font-medium text-horus-text-secondary">Streak Master</p>
              <p class="text-xxs text-horus-text-muted">7-day training streak</p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
