<script setup lang="ts">
import type {
  FlightHourLog,
  ManeuverLog,
  StatsAssessmentResult,
} from '~/composables/useStats'

definePageMeta({
  layout: 'default',
  middleware: 'auth',
})

const { user } = useAuth()
const stats = useStats()
const router = useRouter()

// --- Reactive state ---

interface StudentStatsData {
  totalFlightHours: number
  scenariosCompleted: number
  assessmentsTaken: number
  overallScore: number
  currentStreak: number
}

const statsData = ref<StudentStatsData | null>(null)
const flightHours = ref<FlightHourLog[]>([])
const maneuvers = ref<ManeuverLog[]>([])
const assessmentResults = ref<StatsAssessmentResult[]>([])

const isLoadingStats = ref(true)
const isLoadingFlightHours = ref(true)
const isLoadingManeuvers = ref(true)
const isLoadingAssessments = ref(true)

const flightHoursOffset = ref(0)
const flightHoursHasMore = ref(false)
const isLoadingMoreFlightHours = ref(false)

const maneuversOffset = ref(0)
const maneuversHasMore = ref(false)
const isLoadingMoreManeuvers = ref(false)
const maneuverTypeFilter = ref('all')

const assessmentsOffset = ref(0)
const assessmentsHasMore = ref(false)
const isLoadingMoreAssessments = ref(false)

const errorMessage = ref<string | null>(null)

// --- Data fetching ---

async function fetchStats() {
  isLoadingStats.value = true
  try {
    statsData.value = await stats.getMyStats()
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load statistics'
  }
  finally {
    isLoadingStats.value = false
  }
}

async function fetchFlightHours(loadMore = false) {
  if (loadMore) {
    isLoadingMoreFlightHours.value = true
  }
  else {
    isLoadingFlightHours.value = true
    flightHoursOffset.value = 0
  }

  try {
    const result = await stats.getFlightHours(10, flightHoursOffset.value)
    if (loadMore) {
      flightHours.value = [...flightHours.value, ...result.items]
    }
    else {
      flightHours.value = result.items
    }
    flightHoursHasMore.value = result.hasMore
    flightHoursOffset.value += result.items.length
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load flight hours'
  }
  finally {
    isLoadingFlightHours.value = false
    isLoadingMoreFlightHours.value = false
  }
}

async function fetchManeuvers(loadMore = false) {
  if (loadMore) {
    isLoadingMoreManeuvers.value = true
  }
  else {
    isLoadingManeuvers.value = true
    maneuversOffset.value = 0
  }

  try {
    const typeParam = maneuverTypeFilter.value !== 'all' ? maneuverTypeFilter.value : undefined
    const result = await stats.getManeuvers(12, maneuversOffset.value, typeParam)
    if (loadMore) {
      maneuvers.value = [...maneuvers.value, ...result.items]
    }
    else {
      maneuvers.value = result.items
    }
    maneuversHasMore.value = result.hasMore
    maneuversOffset.value += result.items.length
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load maneuvers'
  }
  finally {
    isLoadingManeuvers.value = false
    isLoadingMoreManeuvers.value = false
  }
}

async function fetchAssessmentResults(loadMore = false) {
  if (loadMore) {
    isLoadingMoreAssessments.value = true
  }
  else {
    isLoadingAssessments.value = true
    assessmentsOffset.value = 0
  }

  try {
    const result = await stats.getAssessmentResults(10, assessmentsOffset.value)
    if (loadMore) {
      assessmentResults.value = [...assessmentResults.value, ...result.items]
    }
    else {
      assessmentResults.value = result.items
    }
    assessmentsHasMore.value = result.hasMore
    assessmentsOffset.value += result.items.length
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load assessment results'
  }
  finally {
    isLoadingAssessments.value = false
    isLoadingMoreAssessments.value = false
  }
}

// --- Helpers ---

const overallScorePercent = computed(() => {
  if (!statsData.value) return 0
  return Math.min(100, Math.max(0, Math.round(statsData.value.overallScore)))
})

const scoreStrokeDash = computed(() => {
  const circumference = 2 * Math.PI * 45
  return `${(overallScorePercent.value / 100) * circumference} ${circumference}`
})

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function getScoreVariant(score: number, max: number): 'success' | 'warning' | 'danger' {
  const pct = max > 0 ? (score / max) * 100 : 0
  if (pct >= 80) return 'success'
  if (pct >= 60) return 'warning'
  return 'danger'
}

function getScoreColor(score: number, max: number): string {
  const pct = max > 0 ? (score / max) * 100 : 0
  if (pct >= 80) return 'text-horus-status-success'
  if (pct >= 60) return 'text-horus-status-warning'
  return 'text-horus-status-danger'
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

function maneuverTypes(): string[] {
  const types = new Set(maneuvers.value.map(m => m.type))
  return ['all', ...Array.from(types)]
}

// Watch filter changes
watch(maneuverTypeFilter, () => {
  fetchManeuvers()
})

onMounted(() => {
  fetchStats()
  fetchFlightHours()
  fetchManeuvers()
  fetchAssessmentResults()
})
</script>

<template>
  <NuxtLayout>
    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <!-- Page Header -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 class="text-xl font-semibold text-horus-text-primary">
              Training Statistics
            </h1>
            <p class="text-sm text-horus-text-secondary mt-1">
              {{ user?.displayName ?? 'Pilot' }}'s performance overview
            </p>
          </div>
          <div v-if="statsData && statsData.currentStreak > 0">
            <HBadge variant="warning" size="md">
              🔥 {{ statsData.currentStreak }} day streak
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

        <!-- Loading State -->
        <div v-if="isLoadingStats" class="flex items-center justify-center py-16">
          <div class="text-center space-y-3">
            <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
            <p class="text-sm text-horus-text-muted">Loading your statistics...</p>
          </div>
        </div>

        <template v-else>
          <!-- Stats Overview Grid -->
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <HStatsCard
              label="Total Flight Hours"
              :value="statsData?.totalFlightHours?.toFixed(1) ?? '0'"
              icon="heroicons:paper-airplane"
              unit="hrs"
              trend="up"
            />
            <HStatsCard
              label="Scenarios Completed"
              :value="String(statsData?.scenariosCompleted ?? 0)"
              icon="heroicons:check-circle"
              trend="up"
            />
            <HStatsCard
              label="Assessments Taken"
              :value="String(statsData?.assessmentsTaken ?? 0)"
              icon="heroicons:clipboard-document-check"
            />

            <!-- Overall Score Card with circular progress -->
            <HCard variant="default" padding="md">
              <div class="flex items-center gap-3">
                <div class="relative w-14 h-14 flex-shrink-0">
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
                      class="text-horus-accent-cyan transition-all duration-700"
                      :stroke-dasharray="scoreStrokeDash"
                    />
                  </svg>
                  <div class="absolute inset-0 flex items-center justify-center">
                    <span class="text-sm font-bold text-horus-text-primary font-mono">
                      {{ overallScorePercent }}
                    </span>
                  </div>
                </div>
                <div>
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
                    Overall Score
                  </p>
                  <p class="text-lg font-bold text-horus-text-primary font-mono mt-0.5">
                    {{ overallScorePercent }}%
                  </p>
                </div>
              </div>
            </HCard>
          </div>

          <!-- Flight Hours Section -->
          <HSection icon="heroicons:clock" title="Flight Hour Log">
            <div v-if="isLoadingFlightHours" class="flex items-center justify-center py-8">
              <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
            </div>

            <div v-else-if="flightHours.length === 0" class="text-center py-8">
              <Icon name="heroicons:clock" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
              <p class="text-sm text-horus-text-muted">No flight hours recorded yet</p>
              <HButton
                variant="primary"
                size="sm"
                icon="heroicons:play"
                class="mt-3"
                @click="router.push('/configurator')"
              >
                Start a Session
              </HButton>
            </div>

            <template v-else>
              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="text-left text-xxs text-horus-text-muted uppercase tracking-wider border-b border-horus-border-subtle">
                      <th class="pb-2 pr-4">Date</th>
                      <th class="pb-2 pr-4">Scenario</th>
                      <th class="pb-2 pr-4">Phase</th>
                      <th class="pb-2 pr-4 text-right">Hours</th>
                      <th class="pb-2 text-right">Maneuvers</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="entry in flightHours"
                      :key="entry.id"
                      class="border-b border-horus-border-subtle/50 hover:bg-horus-bg-tertiary/30 transition-colors"
                    >
                      <td class="py-3 pr-4 text-horus-text-secondary">
                        {{ formatDateShort(entry.date) }}
                      </td>
                      <td class="py-3 pr-4 text-horus-text-primary">
                        {{ entry.scenarioName ?? `Session #${entry.sessionId}` }}
                      </td>
                      <td class="py-3 pr-4">
                        <HBadge variant="info" size="sm">
                          {{ entry.phase }}
                        </HBadge>
                      </td>
                      <td class="py-3 pr-4 text-right font-mono text-horus-accent-cyan">
                        {{ entry.hours.toFixed(1) }}h
                      </td>
                      <td class="py-3 text-right font-mono text-horus-text-secondary">
                        {{ entry.maneuversCount }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div v-if="flightHoursHasMore" class="mt-4 text-center">
                <HButton
                  variant="ghost"
                  size="sm"
                  :loading="isLoadingMoreFlightHours"
                  @click="fetchFlightHours(true)"
                >
                  Load More
                  <Icon name="heroicons:chevron-down" class="w-4 h-4" />
                </HButton>
              </div>
            </template>
          </HSection>

          <!-- Maneuvers Section -->
          <HSection icon="heroicons:arrow-path" title="Maneuver Performance">
            <template #default>
              <div class="space-y-4">
                <!-- Type Filter -->
                <div class="flex items-center gap-2 flex-wrap">
                  <button
                    v-for="mType in maneuverTypes()"
                    :key="mType"
                    :class="[
                      'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                      maneuverTypeFilter === mType
                        ? 'bg-horus-accent-cyan/20 text-horus-accent-cyan border border-horus-accent-cyan/30'
                        : 'bg-horus-bg-tertiary text-horus-text-secondary border border-horus-border-subtle hover:border-horus-accent-cyan/30'
                    ]"
                    @click="maneuverTypeFilter = mType"
                  >
                    {{ mType === 'all' ? 'All Types' : mType }}
                  </button>
                </div>

                <!-- Loading -->
                <div v-if="isLoadingManeuvers" class="flex items-center justify-center py-8">
                  <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
                </div>

                <!-- Empty -->
                <div v-else-if="maneuvers.length === 0" class="text-center py-8">
                  <Icon name="heroicons:arrow-path" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
                  <p class="text-sm text-horus-text-muted">No maneuver data recorded yet</p>
                </div>

                <!-- Grid -->
                <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <HCard
                    v-for="maneuver in maneuvers"
                    :key="maneuver.id"
                    variant="default"
                    padding="sm"
                  >
                    <div class="space-y-2">
                      <div class="flex items-start justify-between">
                        <h4 class="text-sm font-semibold text-horus-text-primary">
                          {{ maneuver.name }}
                        </h4>
                        <span
                          :class="[
                            'text-sm font-bold font-mono',
                            getScoreColor(maneuver.score, maneuver.maxScore)
                          ]"
                        >
                          {{ maneuver.score }}/{{ maneuver.maxScore }}
                        </span>
                      </div>

                      <HProgress
                        :value="maneuver.score"
                        :max="maneuver.maxScore"
                        :variant="getScoreVariant(maneuver.score, maneuver.maxScore)"
                        size="sm"
                        :show-percentage="false"
                      />

                      <div class="flex items-center justify-between text-xxs text-horus-text-muted">
                        <HBadge variant="default" size="sm">
                          {{ maneuver.type }}
                        </HBadge>
                        <span>{{ formatDateShort(maneuver.date) }}</span>
                      </div>
                    </div>
                  </HCard>
                </div>

                <div v-if="maneuversHasMore" class="mt-4 text-center">
                  <HButton
                    variant="ghost"
                    size="sm"
                    :loading="isLoadingMoreManeuvers"
                    @click="fetchManeuvers(true)"
                  >
                    Load More
                    <Icon name="heroicons:chevron-down" class="w-4 h-4" />
                  </HButton>
                </div>
              </div>
            </template>
          </HSection>

          <!-- Assessment Results Section -->
          <HSection icon="heroicons:clipboard-document-check" title="Assessment Results">
            <div v-if="isLoadingAssessments" class="flex items-center justify-center py-8">
              <Icon name="svg-spinners:ring-resize" class="w-6 h-6 text-horus-accent-cyan" />
            </div>

            <div v-else-if="assessmentResults.length === 0" class="text-center py-8">
              <Icon name="heroicons:clipboard-document-check" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
              <p class="text-sm text-horus-text-muted">No assessments completed yet</p>
              <HButton
                variant="primary"
                size="sm"
                icon="heroicons:academic-cap"
                class="mt-3"
                @click="router.push('/assessments')"
              >
                Take an Assessment
              </HButton>
            </div>

            <template v-else>
              <div class="space-y-3">
                <HCard
                  v-for="result in assessmentResults"
                  :key="result.id"
                  variant="default"
                  padding="md"
                >
                  <div class="flex flex-col sm:flex-row sm:items-center gap-4">
                    <!-- Info -->
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <h4 class="text-sm font-semibold text-horus-text-primary truncate">
                          {{ result.assessmentTitle }}
                        </h4>
                        <HBadge
                          :variant="result.passed ? 'active' : 'danger'"
                          size="sm"
                        >
                          {{ result.passed ? 'PASSED' : 'FAILED' }}
                        </HBadge>
                      </div>
                      <div class="flex items-center gap-3 text-xxs text-horus-text-muted">
                        <span>{{ result.module }}</span>
                        <span>•</span>
                        <span>{{ formatDate(result.completedAt) }}</span>
                        <span>•</span>
                        <span>{{ formatDuration(result.timeTakenSeconds) }}</span>
                      </div>
                    </div>

                    <!-- Score -->
                    <div class="flex items-center gap-4 flex-shrink-0">
                      <div class="text-right">
                        <span
                          :class="[
                            'text-lg font-bold font-mono',
                            getScoreColor(result.score, result.maxScore)
                          ]"
                        >
                          {{ result.score }}/{{ result.maxScore }}
                        </span>
                        <p class="text-xxs text-horus-text-muted">
                          {{ result.questionsCorrect }}/{{ result.questionsTotal }} correct
                        </p>
                      </div>

                      <div class="w-24">
                        <HProgress
                          :value="result.score"
                          :max="result.maxScore"
                          :variant="getScoreVariant(result.score, result.maxScore)"
                          size="sm"
                          :show-percentage="false"
                        />
                      </div>

                      <HButton
                        variant="ghost"
                        size="sm"
                        @click="router.push(`/assessments?retake=${result.assessmentId}`)"
                      >
                        Retake
                      </HButton>
                    </div>
                  </div>
                </HCard>
              </div>

              <div v-if="assessmentsHasMore" class="mt-4 text-center">
                <HButton
                  variant="ghost"
                  size="sm"
                  :loading="isLoadingMoreAssessments"
                  @click="fetchAssessmentResults(true)"
                >
                  Load More
                  <Icon name="heroicons:chevron-down" class="w-4 h-4" />
                </HButton>
              </div>
            </template>
          </HSection>
        </template>
      </div>
    </template>

    <template #panel>
      <div class="space-y-6">
        <!-- Quick Stats -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:chart-bar" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">QUICK OVERVIEW</h2>
          </div>

          <div class="space-y-3">
            <HDataPanel
              :value="statsData?.totalFlightHours?.toFixed(1) ?? '0'"
              label="Flight Hours"
              unit="hrs"
              variant="compact"
            />
            <HDataPanel
              :value="String(statsData?.scenariosCompleted ?? 0)"
              label="Completed Scenarios"
              variant="compact"
            />
            <HDataPanel
              :value="`${overallScorePercent}%`"
              label="Overall Score"
              variant="compact"
              :highlight="overallScorePercent >= 80"
            />
          </div>
        </div>

        <!-- Streak Info -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:fire" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">TRAINING STREAK</h2>
          </div>

          <HCard variant="glass" padding="md">
            <div class="text-center space-y-2">
              <p class="text-3xl font-bold text-horus-accent-cyan font-mono">
                {{ statsData?.currentStreak ?? 0 }}
              </p>
              <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
                Current Streak (days)
              </p>
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
              @click="router.push('/configurator')"
            >
              New Session
            </HButton>
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:academic-cap"
              class="w-full justify-start"
              @click="router.push('/assessments')"
            >
              Take Assessment
            </HButton>
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:book-open"
              class="w-full justify-start"
              @click="router.push('/knowledge')"
            >
              Knowledge Base
            </HButton>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
