<script setup lang="ts">
import type { AdminStats, AnalyticsOverview } from '~/composables/useAdmin'

definePageMeta({
  layout: 'admin',
  middleware: ['auth', 'admin'],
})

const admin = useAdmin()

const stats = ref<AdminStats | null>(null)
const overview = ref<AnalyticsOverview | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

async function loadData() {
  isLoading.value = true
  error.value = null
  try {
    const [statsData, overviewData] = await Promise.all([
      admin.fetchStats(),
      admin.fetchAnalyticsOverview(),
    ])
    stats.value = statsData
    overview.value = overviewData
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load admin data'
  }
  finally {
    isLoading.value = false
  }
}

interface StatCard {
  label: string
  key: keyof AdminStats
  icon: string
  color: string
}

const statCards: StatCard[] = [
  { label: 'Organizations', key: 'total_organizations', icon: 'heroicons:building-office-2', color: 'text-horus-accent-cyan' },
  { label: 'Users', key: 'total_users', icon: 'heroicons:users', color: 'text-horus-status-info' },
  { label: 'Sessions', key: 'total_sessions', icon: 'heroicons:play-circle', color: 'text-horus-status-success' },
  { label: 'Scenarios', key: 'total_scenarios', icon: 'heroicons:map', color: 'text-horus-status-warning' },
  { label: 'Active Now', key: 'active_sessions', icon: 'heroicons:signal', color: 'text-horus-status-success' },
]

interface QuickLink {
  path: string
  label: string
  description: string
  icon: string
}

const quickLinks: QuickLink[] = [
  { path: '/admin/organizations', label: 'Organizations', description: 'Manage orgs and seats', icon: 'heroicons:building-office-2' },
  { path: '/admin/users', label: 'Users', description: 'Search and manage users', icon: 'heroicons:users' },
  { path: '/admin/modules', label: 'Modules', description: 'Training curriculum', icon: 'heroicons:academic-cap' },
  { path: '/admin/leaderboard', label: 'Leaderboard', description: 'Analytics & rankings', icon: 'heroicons:trophy' },
]

onMounted(loadData)
</script>

<template>
  <div class="space-y-6 max-w-7xl mx-auto">
    <!-- Page Header -->
    <div>
      <h1 class="text-2xl font-bold text-horus-text-primary">Admin Overview</h1>
      <p class="text-sm text-horus-text-secondary mt-1">Platform-wide statistics and quick access</p>
    </div>

    <!-- Error State -->
    <HCard v-if="error" variant="elevated" padding="lg">
      <div class="flex items-center gap-3 text-horus-status-danger">
        <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 flex-shrink-0" />
        <div class="flex-1">
          <p class="font-medium">Failed to load data</p>
          <p class="text-sm text-horus-text-muted mt-1">{{ error }}</p>
        </div>
        <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadData">
          Retry
        </HButton>
      </div>
    </HCard>

    <!-- Loading State -->
    <div v-else-if="isLoading" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      <HCard v-for="n in 5" :key="n" variant="elevated" padding="md">
        <div class="animate-pulse space-y-3">
          <div class="w-8 h-8 rounded-lg bg-horus-bg-tertiary" />
          <div class="h-6 w-16 rounded bg-horus-bg-tertiary" />
          <div class="h-3 w-24 rounded bg-horus-bg-tertiary" />
        </div>
      </HCard>
    </div>

    <!-- Stats Cards -->
    <template v-else-if="stats">
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <HCard
          v-for="card in statCards"
          :key="card.key"
          variant="elevated"
          padding="md"
          hover
        >
          <div class="space-y-3">
            <div
              :class="[
                'w-10 h-10 rounded-lg flex items-center justify-center',
                card.color === 'text-horus-accent-cyan' && 'bg-horus-accent-cyan/10',
                card.color === 'text-horus-status-info' && 'bg-horus-status-info/10',
                card.color === 'text-horus-status-success' && 'bg-horus-status-success/10',
                card.color === 'text-horus-status-warning' && 'bg-horus-status-warning/10',
              ]"
            >
              <Icon :name="card.icon" :class="['w-5 h-5', card.color]" />
            </div>
            <div>
              <p class="text-2xl font-bold text-horus-text-primary">
                {{ stats[card.key].toLocaleString() }}
              </p>
              <p class="text-xs text-horus-text-muted uppercase tracking-wider mt-0.5">
                {{ card.label }}
              </p>
            </div>
          </div>
        </HCard>
      </div>

      <!-- Quick Links -->
      <HSection title="Quick Access" icon="heroicons:bolt">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <NuxtLink
            v-for="link in quickLinks"
            :key="link.path"
            :to="link.path"
          >
            <HCard variant="elevated" padding="md" hover class="h-full">
              <div class="flex items-start gap-3">
                <div class="w-10 h-10 rounded-lg bg-horus-accent-cyan/10 flex items-center justify-center flex-shrink-0">
                  <Icon :name="link.icon" class="w-5 h-5 text-horus-accent-cyan" />
                </div>
                <div>
                  <p class="text-sm font-semibold text-horus-text-primary">{{ link.label }}</p>
                  <p class="text-xs text-horus-text-muted mt-0.5">{{ link.description }}</p>
                </div>
              </div>
            </HCard>
          </NuxtLink>
        </div>
      </HSection>

      <!-- Recent Activity Summary -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Sessions Overview -->
        <HSection title="Sessions Overview" icon="heroicons:chart-bar">
          <HCard variant="elevated" padding="md">
            <div v-if="overview" class="space-y-4">
              <div class="grid grid-cols-3 gap-4">
                <div>
                  <p class="text-lg font-bold text-horus-text-primary">{{ overview.total_sessions }}</p>
                  <p class="text-xxs text-horus-text-muted uppercase">Total</p>
                </div>
                <div>
                  <p class="text-lg font-bold text-horus-status-success">{{ overview.completed_sessions }}</p>
                  <p class="text-xxs text-horus-text-muted uppercase">Completed</p>
                </div>
                <div>
                  <p class="text-lg font-bold text-horus-accent-cyan">{{ overview.active_sessions }}</p>
                  <p class="text-xxs text-horus-text-muted uppercase">Active</p>
                </div>
              </div>

              <div class="border-t border-horus-border-subtle pt-3">
                <p class="text-xs text-horus-text-muted mb-2">Voice Interactions</p>
                <p class="text-xl font-bold text-horus-text-primary">
                  {{ overview.total_voice_logs.toLocaleString() }}
                </p>
              </div>
            </div>
          </HCard>
        </HSection>

        <!-- Popular Scenarios -->
        <HSection title="Popular Scenarios" icon="heroicons:fire">
          <HCard variant="elevated" padding="md">
            <div v-if="overview && overview.popular_scenarios.length > 0" class="space-y-3">
              <div
                v-for="scenario in overview.popular_scenarios.slice(0, 5)"
                :key="scenario.scenario_id"
                class="flex items-center justify-between py-2 border-b border-horus-border-subtle last:border-0"
              >
                <div class="flex items-center gap-3 min-w-0">
                  <Icon name="heroicons:map" class="w-4 h-4 text-horus-text-muted flex-shrink-0" />
                  <span class="text-sm text-horus-text-primary truncate">{{ scenario.name }}</span>
                </div>
                <HBadge variant="cyan" size="sm">
                  {{ scenario.session_count }} sessions
                </HBadge>
              </div>
            </div>
            <div v-else class="py-6 text-center">
              <Icon name="heroicons:chart-bar" class="w-8 h-8 text-horus-text-muted mx-auto mb-2" />
              <p class="text-sm text-horus-text-muted">No scenario data yet</p>
            </div>
          </HCard>
        </HSection>
      </div>
    </template>
  </div>
</template>
