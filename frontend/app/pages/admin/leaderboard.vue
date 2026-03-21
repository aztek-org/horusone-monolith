<script setup lang="ts">
import type { LeaderboardEntry, AnalyticsOverview } from '~/composables/useAdmin'

definePageMeta({
  layout: 'admin',
  middleware: ['auth', 'admin'],
})

const admin = useAdmin()

const overview = ref<AnalyticsOverview | null>(null)
const leaderboard = ref<LeaderboardEntry[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

async function loadData() {
  isLoading.value = true
  error.value = null
  try {
    const [overviewData, leaderboardData] = await Promise.all([
      admin.fetchAnalyticsOverview(),
      admin.fetchLeaderboard(),
    ])
    overview.value = overviewData
    leaderboard.value = leaderboardData
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load analytics'
  }
  finally {
    isLoading.value = false
  }
}

// Chart helper — compute bar height as percentage of max
const maxDailyCount = computed(() => {
  if (!overview.value?.sessions_by_day.length) return 1
  return Math.max(...overview.value.sessions_by_day.map(d => d.count), 1)
})

function barHeight(count: number): string {
  return `${Math.max((count / maxDailyCount.value) * 100, 4)}%`
}

function formatDuration(ms: number): string {
  const hours = Math.floor(ms / 3_600_000)
  const minutes = Math.floor((ms % 3_600_000) / 60_000)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function rankBadgeVariant(index: number): 'warning' | 'default' | 'info' | 'cyan' {
  if (index === 0) return 'warning'
  if (index === 1) return 'default'
  if (index === 2) return 'info'
  return 'cyan'
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6 max-w-7xl mx-auto">
    <!-- Page Header -->
    <div>
      <h1 class="text-2xl font-bold text-horus-text-primary">Leaderboard & Analytics</h1>
      <p class="text-sm text-horus-text-secondary mt-1">
        Training analytics, engagement metrics, and user rankings
      </p>
    </div>

    <!-- Error -->
    <HCard v-if="error" variant="elevated" padding="lg">
      <div class="flex items-center gap-3 text-horus-status-danger">
        <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 flex-shrink-0" />
        <div class="flex-1">
          <p class="font-medium">{{ error }}</p>
        </div>
        <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadData">
          Retry
        </HButton>
      </div>
    </HCard>

    <!-- Loading -->
    <template v-else-if="isLoading">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <HCard v-for="n in 4" :key="n" variant="elevated" padding="md">
          <div class="animate-pulse space-y-3">
            <div class="h-8 w-16 rounded bg-horus-bg-tertiary" />
            <div class="h-3 w-24 rounded bg-horus-bg-tertiary" />
          </div>
        </HCard>
      </div>
    </template>

    <!-- Content -->
    <template v-else-if="overview">
      <!-- ── Analytics Overview Stats ──────────────────────────────────────── -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <HCard variant="elevated" padding="md" hover>
          <div class="space-y-1">
            <p class="text-2xl font-bold text-horus-text-primary">{{ overview.total_sessions }}</p>
            <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Total Sessions</p>
          </div>
        </HCard>
        <HCard variant="elevated" padding="md" hover>
          <div class="space-y-1">
            <p class="text-2xl font-bold text-horus-status-success">{{ overview.completed_sessions }}</p>
            <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Completed</p>
          </div>
        </HCard>
        <HCard variant="elevated" padding="md" hover>
          <div class="space-y-1">
            <p class="text-2xl font-bold text-horus-accent-cyan">{{ overview.active_sessions }}</p>
            <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Active Now</p>
          </div>
        </HCard>
        <HCard variant="elevated" padding="md" hover>
          <div class="space-y-1">
            <p class="text-2xl font-bold text-horus-status-info">{{ overview.total_voice_logs.toLocaleString() }}</p>
            <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Voice Interactions</p>
          </div>
        </HCard>
      </div>

      <!-- ── Sessions by Day Chart ─────────────────────────────────────────── -->
      <HSection title="Sessions by Day" icon="heroicons:chart-bar">
        <HCard variant="elevated" padding="md">
          <div v-if="overview.sessions_by_day.length > 0" class="space-y-3">
            <!-- Bar Chart -->
            <div class="flex items-end gap-1 h-40">
              <div
                v-for="day in overview.sessions_by_day"
                :key="day.date"
                class="flex-1 flex flex-col items-center justify-end h-full group"
              >
                <!-- Count Tooltip -->
                <span class="text-xxs text-horus-text-muted mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {{ day.count }}
                </span>
                <!-- Bar -->
                <div
                  class="w-full rounded-t bg-horus-accent-cyan/60 hover:bg-horus-accent-cyan transition-colors min-h-[2px]"
                  :style="{ height: barHeight(day.count) }"
                />
              </div>
            </div>

            <!-- X-axis Labels -->
            <div class="flex gap-1">
              <div
                v-for="(day, idx) in overview.sessions_by_day"
                :key="`label-${day.date}`"
                class="flex-1 text-center"
              >
                <span
                  v-if="idx % Math.max(1, Math.floor(overview.sessions_by_day.length / 7)) === 0"
                  class="text-xxs text-horus-text-muted"
                >
                  {{ formatShortDate(day.date) }}
                </span>
              </div>
            </div>
          </div>

          <div v-else class="py-8 text-center">
            <Icon name="heroicons:chart-bar" class="w-8 h-8 text-horus-text-muted mx-auto mb-2" />
            <p class="text-sm text-horus-text-muted">No session data available</p>
          </div>
        </HCard>
      </HSection>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- ── Leaderboard Table ─────────────────────────────────────────── -->
        <div class="lg:col-span-2">
          <HSection title="Leaderboard" icon="heroicons:trophy">
            <HCard variant="elevated" padding="none">
              <div v-if="leaderboard.length === 0" class="py-8 text-center">
                <Icon name="heroicons:trophy" class="w-10 h-10 text-horus-text-muted mx-auto mb-2" />
                <p class="text-sm text-horus-text-muted">No leaderboard data yet</p>
              </div>

              <div v-else class="overflow-x-auto">
                <table class="w-full">
                  <thead>
                    <tr class="border-b border-horus-border-subtle">
                      <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 w-12">
                        #
                      </th>
                      <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                        Pilot
                      </th>
                      <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3">
                        Sessions
                      </th>
                      <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 hidden md:table-cell">
                        Voice Logs
                      </th>
                      <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden md:table-cell">
                        Time
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(entry, idx) in leaderboard"
                      :key="entry.user_id"
                      :class="[
                        'border-b border-horus-border-subtle last:border-0 transition-colors',
                        idx < 3 && 'bg-horus-bg-tertiary/30'
                      ]"
                    >
                      <td class="px-3 py-3 text-center">
                        <HBadge
                          v-if="idx < 3"
                          :variant="rankBadgeVariant(idx)"
                          size="sm"
                        >
                          {{ idx + 1 }}
                        </HBadge>
                        <span v-else class="text-sm text-horus-text-muted">{{ idx + 1 }}</span>
                      </td>
                      <td class="px-4 py-3">
                        <div class="min-w-0">
                          <p class="text-sm font-medium text-horus-text-primary truncate">
                            {{ entry.display_name || 'Unknown Pilot' }}
                          </p>
                          <p class="text-xs text-horus-text-muted truncate">{{ entry.email }}</p>
                        </div>
                      </td>
                      <td class="px-3 py-3 text-center">
                        <span class="text-sm font-semibold text-horus-accent-cyan">
                          {{ entry.completed_sessions }}
                        </span>
                      </td>
                      <td class="px-3 py-3 text-center hidden md:table-cell">
                        <span class="text-sm text-horus-text-primary">
                          {{ entry.total_voice_logs }}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-right hidden md:table-cell">
                        <span class="text-sm text-horus-text-secondary">
                          {{ formatDuration(entry.total_duration_ms) }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </HCard>
          </HSection>
        </div>

        <!-- ── Popular Scenarios ──────────────────────────────────────────── -->
        <div>
          <HSection title="Popular Scenarios" icon="heroicons:fire">
            <HCard variant="elevated" padding="md">
              <div v-if="overview.popular_scenarios.length === 0" class="py-6 text-center">
                <Icon name="heroicons:map" class="w-8 h-8 text-horus-text-muted mx-auto mb-2" />
                <p class="text-sm text-horus-text-muted">No scenario data</p>
              </div>

              <div v-else class="space-y-3">
                <div
                  v-for="(scenario, idx) in overview.popular_scenarios"
                  :key="scenario.scenario_id"
                  class="flex items-center gap-3"
                >
                  <span class="w-6 text-center text-sm font-bold" :class="idx < 3 ? 'text-horus-accent-cyan' : 'text-horus-text-muted'">
                    {{ idx + 1 }}
                  </span>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm text-horus-text-primary truncate">{{ scenario.name }}</p>
                    <div class="mt-1 h-1.5 w-full rounded-full bg-horus-bg-secondary overflow-hidden">
                      <div
                        class="h-full rounded-full bg-horus-accent-cyan/60"
                        :style="{
                          width: `${Math.max((scenario.session_count / Math.max(overview!.popular_scenarios[0].session_count, 1)) * 100, 8)}%`
                        }"
                      />
                    </div>
                  </div>
                  <span class="text-xs text-horus-text-muted flex-shrink-0">
                    {{ scenario.session_count }}
                  </span>
                </div>
              </div>
            </HCard>
          </HSection>
        </div>
      </div>
    </template>
  </div>
</template>
