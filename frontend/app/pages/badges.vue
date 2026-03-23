<script setup lang="ts">
import type { Badge, UserBadge, BadgeCategory, BadgeTier, BadgeProgress } from '~/composables/useGamification'

definePageMeta({
  layout: 'default',
  middleware: 'auth',
})

const gamification = useGamification()

const allBadges = ref<Badge[]>([])
const myBadges = ref<UserBadge[]>([])
const badgeProgress = ref<BadgeProgress[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

async function loadData() {
  isLoading.value = true
  error.value = null
  try {
    const [allData, myData, progressData] = await Promise.all([
      gamification.getAllBadges(),
      gamification.getMyBadges(),
      gamification.getBadgeProgress(),
    ])
    allBadges.value = allData
    myBadges.value = myData
    badgeProgress.value = progressData
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load badges'
  }
  finally {
    isLoading.value = false
  }
}

const earnedBadgeIds = computed(() =>
  new Set(myBadges.value.map(ub => ub.badge_id)),
)

const earnedBadgeMap = computed(() => {
  const map = new Map<string, UserBadge>()
  for (const ub of myBadges.value) {
    map.set(ub.badge_id, ub)
  }
  return map
})

const progressMap = computed(() => {
  const map = new Map<string, BadgeProgress>()
  for (const bp of badgeProgress.value) {
    map.set(bp.badge_id, bp)
  }
  return map
})

// Badge categories with their badges grouped
const categoryConfig: { key: BadgeCategory; label: string; icon: string }[] = [
  { key: 'flight', label: 'Flight', icon: '✈️' },
  { key: 'communication', label: 'Communication', icon: '📡' },
  { key: 'knowledge', label: 'Knowledge', icon: '📚' },
  { key: 'streak', label: 'Streak', icon: '🔥' },
  { key: 'achievement', label: 'Achievement', icon: '🏆' },
]

const badgesByCategory = computed(() => {
  const grouped = new Map<BadgeCategory, Badge[]>()
  for (const cat of categoryConfig) {
    grouped.set(cat.key, [])
  }
  for (const badge of allBadges.value) {
    const list = grouped.get(badge.category) ?? []
    list.push(badge)
    grouped.set(badge.category, list)
  }
  return grouped
})

// Stats
const totalBadges = computed(() => allBadges.value.length)
const earnedCount = computed(() => myBadges.value.length)
const completionPercent = computed(() =>
  totalBadges.value > 0 ? Math.round((earnedCount.value / totalBadges.value) * 100) : 0,
)

const tierCounts = computed(() => {
  const counts: Record<BadgeTier, number> = { bronze: 0, silver: 0, gold: 0, platinum: 0 }
  for (const ub of myBadges.value) {
    counts[ub.badge.tier]++
  }
  return counts
})

const tierConfig: { key: BadgeTier; label: string; emoji: string; color: string }[] = [
  { key: 'bronze', label: 'Bronze', emoji: '🥉', color: 'text-amber-600' },
  { key: 'silver', label: 'Silver', emoji: '🥈', color: 'text-gray-300' },
  { key: 'gold', label: 'Gold', emoji: '🥇', color: 'text-yellow-400' },
  { key: 'platinum', label: 'Platinum', emoji: '💎', color: 'text-blue-200' },
]

function getBadgeProgress(badgeId: string): number {
  return progressMap.value.get(badgeId)?.progress_percent ?? 0
}

function isEarned(badgeId: string): boolean {
  return earnedBadgeIds.value.has(badgeId)
}

function getEarnedAt(badgeId: string): string | null {
  return earnedBadgeMap.value.get(badgeId)?.earned_at ?? null
}

onMounted(loadData)
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader title="Badge Gallery" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO" />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6 max-w-7xl mx-auto">
        <!-- Page Header -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold text-horus-text-primary">Badge Gallery</h1>
            <p class="text-sm text-horus-text-secondary mt-1">
              Earn badges by completing training milestones
            </p>
          </div>
          <NuxtLink to="/leaderboard">
            <HButton variant="secondary" size="sm" icon="heroicons:trophy">
              Leaderboard
            </HButton>
          </NuxtLink>
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
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <HCard v-for="n in 4" :key="n" variant="elevated" padding="md">
              <div class="animate-pulse space-y-3">
                <div class="h-8 w-16 rounded bg-horus-bg-tertiary" />
                <div class="h-3 w-24 rounded bg-horus-bg-tertiary" />
              </div>
            </HCard>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            <HCard v-for="n in 8" :key="`badge-${n}`" variant="elevated" padding="md">
              <div class="animate-pulse space-y-3">
                <div class="w-12 h-12 rounded-xl bg-horus-bg-tertiary" />
                <div class="h-4 w-20 rounded bg-horus-bg-tertiary" />
                <div class="h-3 w-32 rounded bg-horus-bg-tertiary" />
              </div>
            </HCard>
          </div>
        </template>

        <!-- Content -->
        <template v-else>
          <!-- Stats Summary -->
          <div class="grid grid-cols-2 lg:grid-cols-6 gap-4">
            <!-- Overall Progress -->
            <HCard variant="elevated" padding="md" class="col-span-2">
              <div class="space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Overall Progress</span>
                  <span class="text-sm font-bold text-horus-accent-cyan font-mono">
                    {{ earnedCount }}/{{ totalBadges }}
                  </span>
                </div>
                <HProgress
                  :value="earnedCount"
                  :max="totalBadges"
                  :show-percentage="true"
                  variant="default"
                  size="md"
                />
              </div>
            </HCard>

            <!-- Tier Counts -->
            <HCard
              v-for="tier in tierConfig"
              :key="tier.key"
              variant="elevated"
              padding="md"
              hover
            >
              <div class="text-center space-y-1">
                <span class="text-2xl">{{ tier.emoji }}</span>
                <p :class="['text-xl font-bold font-mono', tier.color]">
                  {{ tierCounts[tier.key] }}
                </p>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
                  {{ tier.label }}
                </p>
              </div>
            </HCard>
          </div>

          <!-- My Earned Badges -->
          <HSection
            v-if="myBadges.length > 0"
            title="My Badges"
            icon="heroicons:star"
          >
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              <HBadgeCard
                v-for="ub in myBadges"
                :key="ub.id"
                :name="ub.badge.name"
                :description="ub.badge.description"
                :icon="ub.badge.icon"
                :tier="ub.badge.tier"
                :category="ub.badge.category"
                :earned="true"
                :earned-at="ub.earned_at"
              />
            </div>
          </HSection>

          <!-- All Badges by Category -->
          <template v-for="catConfig in categoryConfig" :key="catConfig.key">
            <HSection
              v-if="(badgesByCategory.get(catConfig.key) ?? []).length > 0"
              :title="`${catConfig.icon} ${catConfig.label}`"
            >
              <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                <HBadgeCard
                  v-for="badge in badgesByCategory.get(catConfig.key)"
                  :key="badge.id"
                  :name="badge.name"
                  :description="badge.description"
                  :icon="badge.icon"
                  :tier="badge.tier"
                  :category="badge.category"
                  :earned="isEarned(badge.id)"
                  :earned-at="getEarnedAt(badge.id)"
                  :progress="isEarned(badge.id) ? 100 : getBadgeProgress(badge.id)"
                />
              </div>
            </HSection>
          </template>

          <!-- Empty State -->
          <div
            v-if="allBadges.length === 0"
            class="text-center py-12"
          >
            <Icon name="heroicons:star" class="w-12 h-12 text-horus-text-muted mx-auto mb-3" />
            <p class="text-lg font-medium text-horus-text-secondary">No badges available yet</p>
            <p class="text-sm text-horus-text-muted mt-1">
              Badges will appear here as the platform grows
            </p>
          </div>
        </template>
      </div>
    </template>

    <template #panel>
      <div class="space-y-6">
        <!-- Badge Info -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">HOW TO EARN</h2>
          </div>
          <div class="space-y-2 text-xs text-horus-text-secondary">
            <p>Complete training sessions, improve your scores, and maintain streaks to earn badges.</p>
            <p>Badges come in four tiers: Bronze, Silver, Gold, and Platinum.</p>
            <p>Higher tiers require more dedication and skill.</p>
          </div>
        </div>

        <!-- Category Legend -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:tag" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">CATEGORIES</h2>
          </div>
          <div class="space-y-2">
            <div
              v-for="cat in categoryConfig"
              :key="cat.key"
              class="flex items-center gap-2 p-2 rounded-lg bg-horus-bg-tertiary/30"
            >
              <span class="text-lg">{{ cat.icon }}</span>
              <div>
                <p class="text-xs font-medium text-horus-text-primary">{{ cat.label }}</p>
                <p class="text-xxs text-horus-text-muted">
                  {{ (badgesByCategory.get(cat.key) ?? []).length }} badges
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
