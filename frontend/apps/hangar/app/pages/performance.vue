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

type TrendMetric = 'score' | 'time'

const api = useApi()

const sessions = ref<TrainingSession[]>([])
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const timeRange = ref('week')
const trendMetric = ref<TrendMetric>('score')
const streakGoal = 7
let latestFetchRequest = 0

function buildSessionsPath(): string {
  const params = new URLSearchParams({
    limit: '500',
    started_after: rangeStartDate().toISOString(),
  })
  return `/api/v1/sessions?${params.toString()}`
}

async function fetchSessions() {
  const requestId = ++latestFetchRequest
  isLoading.value = true
  errorMessage.value = null
  try {
    const data = await api.get<TrainingSession[]>(buildSessionsPath())
    if (requestId !== latestFetchRequest) return
    sessions.value = data
  }
  catch (err) {
    if (requestId !== latestFetchRequest) return
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load sessions'
  }
  finally {
    if (requestId !== latestFetchRequest) return
    isLoading.value = false
  }
}

function rangeStartDate(): Date {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  if (timeRange.value === 'day') return start
  if (timeRange.value === 'month') {
    start.setDate(start.getDate() - 29)
    return start
  }
  start.setDate(start.getDate() - 6)
  return start
}

const filteredSessions = computed(() => sessions.value)

const rangeLabel = computed(() => {
  if (timeRange.value === 'day') return 'today'
  if (timeRange.value === 'month') return 'the last 30 days'
  return 'the last 7 days'
})

const completedSessions = computed(() =>
  filteredSessions.value.filter(s => s.status === 'completed'),
)

const activeSessions = computed(() =>
  filteredSessions.value.filter(s => s.status === 'active'),
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
    value: filteredSessions.value.length,
    trend: filteredSessions.value.length > 0 ? 'up' as const : 'stable' as const,
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
  [...filteredSessions.value]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 5),
)

interface TrendPoint {
  label: string
  sessions: number
  completed: number
  score: number
  avgDuration: number
}

function dayKey(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function daysBetween(a: Date, b: Date): number {
  const msPerDay = 24 * 60 * 60 * 1000
  return Math.round((b.getTime() - a.getTime()) / msPerDay)
}

const activityDays = computed(() => {
  const keys = new Set<string>()
  for (const session of sessions.value) {
    keys.add(dayKey(new Date(session.started_at)))
  }
  return Array.from(keys)
    .map((key) => {
      const [year, month, day] = key.split('-').map(Number)
      return new Date(year, month - 1, day)
    })
    .sort((a, b) => a.getTime() - b.getTime())
})

const streakStats = computed(() => {
  const dates = activityDays.value
  if (dates.length === 0) {
    return { current: 0, best: 0 }
  }

  let best = 1
  let running = 1
  for (let i = 1; i < dates.length; i++) {
    if (daysBetween(dates[i - 1]!, dates[i]!) === 1) {
      running += 1
    }
    else {
      running = 1
    }
    best = Math.max(best, running)
  }

  const keySet = new Set(dates.map(date => dayKey(date)))
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  let cursor = new Date(today)

  if (!keySet.has(dayKey(cursor))) {
    cursor.setDate(cursor.getDate() - 1)
    if (!keySet.has(dayKey(cursor))) {
      return { current: 0, best }
    }
  }

  let current = 0
  while (keySet.has(dayKey(cursor))) {
    current += 1
    cursor.setDate(cursor.getDate() - 1)
  }

  return { current, best }
})

function rangeDays(): number {
  if (timeRange.value === 'day') return 1
  if (timeRange.value === 'month') return 30
  return 7
}

const trendPoints = computed<TrendPoint[]>(() => {
  const days = rangeDays()
  const startDate = rangeStartDate()

  const buckets = new Map<string, {
    date: Date
    sessions: number
    completed: number
    durationTotal: number
    durationCount: number
  }>()

  for (let i = 0; i < days; i++) {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() + i)
    const key = dayKey(date)
    buckets.set(key, {
      date,
      sessions: 0,
      completed: 0,
      durationTotal: 0,
      durationCount: 0,
    })
  }

  for (const session of filteredSessions.value) {
    const startedAt = new Date(session.started_at)
    if (startedAt < startDate) continue
    const bucket = buckets.get(dayKey(startedAt))
    if (!bucket) continue
    bucket.sessions += 1

    if (session.status === 'completed' && session.ended_at) {
      bucket.completed += 1
      const durationMinutes = Math.max(
        0,
        Math.round((new Date(session.ended_at).getTime() - startedAt.getTime()) / 60000),
      )
      bucket.durationTotal += durationMinutes
      bucket.durationCount += 1
    }
  }

  return Array.from(buckets.values()).map(({ date, sessions, completed, durationTotal, durationCount }) => {
    const score = sessions > 0 ? Math.round((completed / sessions) * 100) : 0
    const avgDuration = durationCount > 0 ? Math.round(durationTotal / durationCount) : 0
    return {
      label: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      sessions,
      completed,
      score,
      avgDuration,
    }
  })
})

function trendValue(point: TrendPoint): number {
  return trendMetric.value === 'score' ? point.score : point.avgDuration
}

const trendMetricMax = computed(() => {
  if (trendMetric.value === 'score') return 100
  const maxValue = Math.max(0, ...trendPoints.value.map(point => point.avgDuration))
  return maxValue > 0 ? maxValue : 10
})

function trendBarHeight(point: TrendPoint): number {
  const value = trendValue(point)
  if (value <= 0) return 0
  const maxValue = trendMetricMax.value
  if (maxValue <= 0) return 0
  const normalized = Math.round((value / maxValue) * 100)
  return Math.max(6, Math.min(100, normalized))
}

function showTrendLabel(index: number): boolean {
  if (timeRange.value !== 'month') return true
  return index % 5 === 0 || index === trendPoints.value.length - 1
}

function trendBarTitle(point: TrendPoint): string {
  if (trendMetric.value === 'score') {
    return `${point.label}: ${point.score}% completion (${point.completed}/${point.sessions})`
  }
  return `${point.label}: ${point.avgDuration} min avg duration (${point.completed} completed)`
}

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

function sessionPath(session: TrainingSession): string {
  return session.status === 'completed'
    ? `/session/${session.id}`
    : `/mission/${session.id}`
}

onMounted(() => {
  fetchSessions()
})

watch(timeRange, () => {
  fetchSessions()
})
</script>

<template>
  <NuxtLayout name="default">
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
          <h3 class="text-xs font-semibold text-horus-text-secondary uppercase">Recent Sessions ({{ rangeLabel }})</h3>

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
              :to="sessionPath(session)"
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
                    Based on {{ filteredSessions.length }} training session{{ filteredSessions.length === 1 ? '' : 's' }} in {{ rangeLabel }}.
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

          <!-- Performance Trend -->
          <HCard variant="glass" padding="lg">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-semibold text-horus-text-primary">Performance Trend</h3>
              <HButtonGroup
                v-model="trendMetric"
                :options="[
                  { value: 'score', label: 'Score' },
                  { value: 'time', label: 'Time' }
                ]"
                size="sm"
              />
            </div>
            <div class="h-64 border border-horus-border-subtle rounded-lg p-4">
              <div v-if="trendPoints.every(point => point.sessions === 0)" class="h-full flex items-center justify-center">
                <div class="text-center text-horus-text-muted">
                  <Icon name="heroicons:chart-bar" class="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p class="text-sm">No session activity in this range</p>
                </div>
              </div>
              <div v-else class="h-full flex items-end gap-1">
                <div
                  v-for="(point, index) in trendPoints"
                  :key="`${point.label}-${index}`"
                  class="h-full flex-1 flex flex-col justify-end items-center"
                >
                  <div
                    :class="[
                      'w-full rounded-t transition-all duration-300',
                      trendMetric === 'score' ? 'bg-horus-accent-cyan/80' : 'bg-horus-status-warning/80',
                    ]"
                    :style="{ height: `${trendBarHeight(point)}%` }"
                    :title="trendBarTitle(point)"
                  />
                  <span v-if="showTrendLabel(index)" class="mt-1 text-[10px] text-horus-text-muted">
                    {{ point.label }}
                  </span>
                </div>
              </div>
            </div>
            <p class="mt-3 text-xs text-horus-text-muted">
              {{ trendMetric === 'score' ? 'Completion score by day (%)' : 'Average completed-session duration by day (minutes)' }}
            </p>
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

          <div
            :class="[
              'flex items-center gap-3 p-3 rounded-lg border',
              streakStats.current >= streakGoal
                ? 'bg-horus-status-warning/10 border-horus-status-warning/30'
                : 'bg-horus-bg-tertiary/50 border-horus-border-subtle opacity-70',
            ]"
          >
            <Icon
              name="heroicons:fire"
              :class="[
                'w-8 h-8',
                streakStats.current >= streakGoal ? 'text-horus-status-warning' : 'text-horus-text-muted',
              ]"
            />
            <div>
              <p
                :class="[
                  'text-sm font-medium',
                  streakStats.current >= streakGoal ? 'text-horus-text-primary' : 'text-horus-text-secondary',
                ]"
              >
                Streak Master
              </p>
              <p class="text-xxs text-horus-text-muted">
                Current {{ streakStats.current }} day{{ streakStats.current === 1 ? '' : 's' }}
                · Best {{ streakStats.best }} day{{ streakStats.best === 1 ? '' : 's' }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
