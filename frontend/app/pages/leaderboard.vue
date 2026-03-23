<script setup lang="ts">
import type { LeaderboardEntry, LeaderboardPeriod, LeaderboardCategory, UserBadge } from '~/composables/useGamification'

definePageMeta({
  layout: false,
  middleware: 'auth',
})

const { user } = useAuth()
const gamification = useGamification()

const entries = ref<LeaderboardEntry[]>([])
const recentBadges = ref<UserBadge[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const selectedPeriod = ref<LeaderboardPeriod>('monthly')
const selectedCategory = ref<LeaderboardCategory>('overall')

const currentUserId = computed(() => user.value?.keycloakId ?? null)

const periods: { value: LeaderboardPeriod; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'all_time', label: 'All Time' },
]

const categories: { value: LeaderboardCategory; label: string }[] = [
  { value: 'overall', label: 'Overall' },
  { value: 'communication', label: 'Communication' },
  { value: 'decision_making', label: 'Decision Making' },
  { value: 'procedures', label: 'Procedures' },
]

async function loadData() {
  isLoading.value = true
  error.value = null
  try {
    const [leaderboardData, badgesData] = await Promise.all([
      gamification.getLeaderboard(selectedPeriod.value, undefined, selectedCategory.value, 50),
      gamification.getMyBadges(),
    ])
    entries.value = leaderboardData
    recentBadges.value = badgesData.slice(-5).reverse()
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load leaderboard'
  }
  finally {
    isLoading.value = false
  }
}

async function loadLeaderboard() {
  isLoading.value = true
  error.value = null
  try {
    entries.value = await gamification.getLeaderboard(selectedPeriod.value, undefined, selectedCategory.value, 50)
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load leaderboard'
  }
  finally {
    isLoading.value = false
  }
}

const podium = computed(() => entries.value.slice(0, 3))
const restOfLeaderboard = computed(() => entries.value.slice(3))

const podiumStyles: Record<number, { size: string; border: string; textColor: string; label: string; emoji: string }> = {
  0: { size: 'w-20 h-20', border: 'border-yellow-400 ring-2 ring-yellow-400/30', textColor: 'text-yellow-400', label: '1st Place', emoji: '🥇' },
  1: { size: 'w-16 h-16', border: 'border-gray-300 ring-2 ring-gray-300/30', textColor: 'text-gray-300', label: '2nd Place', emoji: '🥈' },
  2: { size: 'w-16 h-16', border: 'border-amber-600 ring-2 ring-amber-600/30', textColor: 'text-amber-600', label: '3rd Place', emoji: '🥉' },
}

function formatBadgeDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

watch([selectedPeriod, selectedCategory], () => {
  loadLeaderboard()
})

onMounted(loadData)
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader title="Training Leaderboard" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO" />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6 max-w-7xl mx-auto">
        <!-- Page Header -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-horus-text-primary">Training Leaderboard</h1>
            <p class="text-sm text-horus-text-secondary mt-1">
              Rankings, achievements, and training statistics
            </p>
          </div>

          <!-- Period Selector -->
          <div class="flex items-center gap-1 bg-horus-bg-secondary rounded-lg p-1 border border-horus-border-subtle">
            <button
              v-for="period in periods"
              :key="period.value"
              :class="[
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
                selectedPeriod === period.value
                  ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border border-horus-accent-cyan/20'
                  : 'text-horus-text-muted hover:text-horus-text-primary border border-transparent',
              ]"
              @click="selectedPeriod = period.value"
            >
              {{ period.label }}
            </button>
          </div>
        </div>

        <!-- Error State -->
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

        <!-- Loading State -->
        <template v-else-if="isLoading">
          <div class="grid grid-cols-3 gap-4 max-w-2xl mx-auto">
            <HCard v-for="n in 3" :key="n" variant="elevated" padding="lg">
              <div class="animate-pulse flex flex-col items-center space-y-3">
                <div class="w-16 h-16 rounded-full bg-horus-bg-tertiary" />
                <div class="h-4 w-24 rounded bg-horus-bg-tertiary" />
                <div class="h-6 w-16 rounded bg-horus-bg-tertiary" />
              </div>
            </HCard>
          </div>
        </template>

        <!-- Content -->
        <template v-else>
          <!-- Podium (Top 3) -->
          <div v-if="podium.length > 0" class="max-w-3xl mx-auto">
            <div class="grid grid-cols-3 gap-4 items-end">
              <!-- 2nd Place -->
              <div v-if="podium[1]" class="flex flex-col items-center">
                <HCard variant="elevated" padding="md" class="w-full text-center">
                  <div class="flex flex-col items-center space-y-3">
                    <span class="text-2xl">{{ podiumStyles[1].emoji }}</span>
                    <div
                      :class="[
                        'rounded-full border-2 overflow-hidden bg-horus-bg-tertiary',
                        podiumStyles[1].size,
                        podiumStyles[1].border,
                      ]"
                    >
                      <img
                        :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${podium[1].avatar_seed || podium[1].user_id}`"
                        :alt="podium[1].display_name"
                        class="w-full h-full object-cover"
                      />
                    </div>
                    <div>
                      <p class="text-sm font-semibold text-horus-text-primary truncate max-w-[150px]">
                        {{ podium[1].display_name }}
                      </p>
                      <p :class="['text-lg font-bold font-mono', podiumStyles[1].textColor]">
                        {{ podium[1].total_score.toLocaleString() }}
                      </p>
                      <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
                        {{ podiumStyles[1].label }}
                      </p>
                    </div>
                  </div>
                </HCard>
              </div>
              <div v-else />

              <!-- 1st Place (Center, larger) -->
              <div v-if="podium[0]" class="flex flex-col items-center">
                <HCard variant="elevated" padding="lg" class="w-full text-center border-yellow-400/20">
                  <div class="flex flex-col items-center space-y-3">
                    <span class="text-3xl">{{ podiumStyles[0].emoji }}</span>
                    <div
                      :class="[
                        'rounded-full border-2 overflow-hidden bg-horus-bg-tertiary',
                        podiumStyles[0].size,
                        podiumStyles[0].border,
                      ]"
                    >
                      <img
                        :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${podium[0].avatar_seed || podium[0].user_id}`"
                        :alt="podium[0].display_name"
                        class="w-full h-full object-cover"
                      />
                    </div>
                    <div>
                      <p class="text-base font-bold text-horus-text-primary truncate max-w-[180px]">
                        {{ podium[0].display_name }}
                      </p>
                      <p :class="['text-2xl font-bold font-mono', podiumStyles[0].textColor]">
                        {{ podium[0].total_score.toLocaleString() }}
                      </p>
                      <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
                        {{ podiumStyles[0].label }}
                      </p>
                    </div>
                  </div>
                </HCard>
              </div>
              <div v-else />

              <!-- 3rd Place -->
              <div v-if="podium[2]" class="flex flex-col items-center">
                <HCard variant="elevated" padding="md" class="w-full text-center">
                  <div class="flex flex-col items-center space-y-3">
                    <span class="text-2xl">{{ podiumStyles[2].emoji }}</span>
                    <div
                      :class="[
                        'rounded-full border-2 overflow-hidden bg-horus-bg-tertiary',
                        podiumStyles[2].size,
                        podiumStyles[2].border,
                      ]"
                    >
                      <img
                        :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${podium[2].avatar_seed || podium[2].user_id}`"
                        :alt="podium[2].display_name"
                        class="w-full h-full object-cover"
                      />
                    </div>
                    <div>
                      <p class="text-sm font-semibold text-horus-text-primary truncate max-w-[150px]">
                        {{ podium[2].display_name }}
                      </p>
                      <p :class="['text-lg font-bold font-mono', podiumStyles[2].textColor]">
                        {{ podium[2].total_score.toLocaleString() }}
                      </p>
                      <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
                        {{ podiumStyles[2].label }}
                      </p>
                    </div>
                  </div>
                </HCard>
              </div>
              <div v-else />
            </div>
          </div>

          <!-- Category Tabs -->
          <div class="flex items-center gap-1 border-b border-horus-border-subtle">
            <button
              v-for="cat in categories"
              :key="cat.value"
              :class="[
                'px-4 py-2.5 text-sm font-medium transition-all duration-200 border-b-2 -mb-px',
                selectedCategory === cat.value
                  ? 'border-horus-accent-cyan text-horus-accent-cyan'
                  : 'border-transparent text-horus-text-muted hover:text-horus-text-primary hover:border-horus-border-default',
              ]"
              @click="selectedCategory = cat.value"
            >
              {{ cat.label }}
            </button>
          </div>

          <!-- Full Rankings Table -->
          <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div class="lg:col-span-3">
              <HLeaderboardTable
                :entries="entries"
                :current-user-id="currentUserId"
                :show-badges="true"
              />
            </div>

            <!-- Achievements Feed Sidebar -->
            <div>
              <HSection title="Recent Achievements" icon="heroicons:star">
                <HCard variant="elevated" padding="md">
                  <div v-if="recentBadges.length === 0" class="py-6 text-center">
                    <Icon name="heroicons:star" class="w-8 h-8 text-horus-text-muted mx-auto mb-2" />
                    <p class="text-sm text-horus-text-muted">No recent achievements</p>
                  </div>

                  <div v-else class="space-y-3">
                    <div
                      v-for="badge in recentBadges"
                      :key="badge.id"
                      class="flex items-start gap-3 p-2 rounded-lg bg-horus-bg-tertiary/30"
                    >
                      <span class="text-xl flex-shrink-0">{{ badge.badge.icon }}</span>
                      <div class="min-w-0 flex-1">
                        <p class="text-xs font-medium text-horus-text-primary truncate">
                          {{ badge.badge.name }}
                        </p>
                        <p class="text-xxs text-horus-text-muted mt-0.5">
                          Earned {{ formatBadgeDate(badge.earned_at) }}
                        </p>
                      </div>
                    </div>
                  </div>

                  <NuxtLink
                    to="/badges"
                    class="mt-4 flex items-center justify-center gap-1 text-xs text-horus-accent-cyan hover:text-horus-accent-cyan-glow transition-colors"
                  >
                    View all badges
                    <Icon name="heroicons:arrow-right" class="w-3 h-3" />
                  </NuxtLink>
                </HCard>
              </HSection>
            </div>
          </div>
        </template>
      </div>
    </template>
  </NuxtLayout>
</template>
