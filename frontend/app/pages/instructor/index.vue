<script setup lang="ts">
import type { InstructorStudent, InstructorStats, RecentSession } from '~/composables/useInstructor'

definePageMeta({
  layout: false,
  middleware: ['auth', 'instructor'],
})

const { user } = useAuth()
const instructor = useInstructor()
const router = useRouter()

const stats = ref<InstructorStats | null>(null)
const students = ref<InstructorStudent[]>([])
const recentSessions = ref<RecentSession[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const selectedPeriod = ref<'week' | 'month' | 'all'>('month')

interface StatCard {
  label: string
  key: keyof InstructorStats
  icon: string
  color: string
  bgColor: string
}

const statCards: StatCard[] = [
  { label: 'Total Students', key: 'total_students', icon: 'heroicons:users', color: 'text-horus-accent-cyan', bgColor: 'bg-horus-accent-cyan/10' },
  { label: 'Active Sessions', key: 'active_sessions', icon: 'heroicons:play-circle', color: 'text-horus-status-success', bgColor: 'bg-horus-status-success/10' },
  { label: 'Avg. Student Score', key: 'average_student_score', icon: 'heroicons:chart-bar', color: 'text-horus-status-warning', bgColor: 'bg-horus-status-warning/10' },
  { label: 'Assessments Created', key: 'assessments_created', icon: 'heroicons:clipboard-document-check', color: 'text-horus-status-info', bgColor: 'bg-horus-status-info/10' },
]

interface QuickAction {
  label: string
  description: string
  path: string
  icon: string
}

const quickActions: QuickAction[] = [
  { label: 'Create Scenario', description: 'Build a new training scenario', path: '/configurator', icon: 'heroicons:cog-6-tooth' },
  { label: 'View Leaderboard', description: 'Student rankings & stats', path: '/leaderboard', icon: 'heroicons:trophy' },
  { label: 'Badge Gallery', description: 'All available badges', path: '/badges', icon: 'heroicons:star' },
  { label: 'My Profile', description: 'Manage instructor profile', path: '/instructor/profile', icon: 'heroicons:user-circle' },
]

async function loadData() {
  isLoading.value = true
  error.value = null
  try {
    const [statsData, studentsData, sessionsData] = await Promise.all([
      instructor.getMyStats(),
      instructor.getMyStudents(),
      instructor.getRecentSessions(10),
    ])
    stats.value = statsData
    students.value = studentsData
    recentSessions.value = sessionsData
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load instructor data'
  }
  finally {
    isLoading.value = false
  }
}

const topStudents = computed(() => {
  return [...students.value]
    .sort((a, b) => b.overall_score - a.overall_score)
    .slice(0, 5)
})

function formatStatValue(key: keyof InstructorStats, value: number): string {
  if (key === 'average_student_score') return `${value.toFixed(1)}%`
  return value.toLocaleString()
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getStatusVariant(status: string): 'success' | 'active' | 'warning' {
  if (status === 'completed') return 'success'
  if (status === 'active') return 'active'
  return 'warning'
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-horus-status-success'
  if (score >= 60) return 'text-horus-status-warning'
  return 'text-horus-status-danger'
}

function handleStudentClick(studentId: string) {
  router.push(`/instructor/students/${studentId}`)
}

onMounted(loadData)
</script>

<template>
  <NuxtLayout name="default">
    <template #header>
      <AppHeader title="Instructor Dashboard" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO" />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6 max-w-7xl mx-auto">
        <!-- Page Header -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold text-horus-text-primary">
              Instructor Dashboard
            </h1>
            <p class="text-sm text-horus-text-secondary mt-1">
              Welcome back, {{ user?.displayName ?? 'Instructor' }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <HBadge variant="info" size="sm">
              INSTRUCTOR
            </HBadge>
          </div>
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
        <div v-else-if="isLoading" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <HCard v-for="n in 4" :key="n" variant="elevated" padding="md">
            <div class="animate-pulse space-y-3">
              <div class="w-10 h-10 rounded-lg bg-horus-bg-tertiary" />
              <div class="h-6 w-16 rounded bg-horus-bg-tertiary" />
              <div class="h-3 w-24 rounded bg-horus-bg-tertiary" />
            </div>
          </HCard>
        </div>

        <!-- Content -->
        <template v-else-if="stats">
          <!-- Stats Overview -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
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
                    card.bgColor,
                  ]"
                >
                  <Icon :name="card.icon" :class="['w-5 h-5', card.color]" />
                </div>
                <div>
                  <p class="text-2xl font-bold text-horus-text-primary font-mono">
                    {{ formatStatValue(card.key, stats[card.key]) }}
                  </p>
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider mt-0.5">
                    {{ card.label }}
                  </p>
                </div>
              </div>
            </HCard>
          </div>

          <!-- Quick Actions -->
          <HSection title="Quick Actions" icon="heroicons:bolt">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <NuxtLink
                v-for="action in quickActions"
                :key="action.path"
                :to="action.path"
              >
                <HCard variant="elevated" padding="md" hover class="h-full">
                  <div class="flex items-start gap-3">
                    <div class="w-10 h-10 rounded-lg bg-horus-accent-cyan/10 flex items-center justify-center flex-shrink-0">
                      <Icon :name="action.icon" class="w-5 h-5 text-horus-accent-cyan" />
                    </div>
                    <div>
                      <p class="text-sm font-semibold text-horus-text-primary">{{ action.label }}</p>
                      <p class="text-xs text-horus-text-muted mt-0.5">{{ action.description }}</p>
                    </div>
                  </div>
                </HCard>
              </NuxtLink>
            </div>
          </HSection>

          <!-- Student Roster -->
          <HSection title="Student Roster" icon="heroicons:users">
            <StudentRoster
              :students="students"
              @student-click="handleStudentClick"
            />
          </HSection>

          <!-- Bottom Grid: Recent Sessions + Top Performers -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Recent Sessions -->
            <div class="lg:col-span-2">
              <HSection title="Recent Sessions" icon="heroicons:clock">
                <HCard variant="elevated" padding="none">
                  <div v-if="recentSessions.length === 0" class="py-8 text-center">
                    <Icon name="heroicons:clock" class="w-10 h-10 text-horus-text-muted mx-auto mb-2" />
                    <p class="text-sm text-horus-text-muted">No recent sessions</p>
                  </div>

                  <div v-else class="overflow-x-auto">
                    <table class="w-full">
                      <thead>
                        <tr class="border-b border-horus-border-subtle">
                          <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                            Student
                          </th>
                          <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 hidden md:table-cell">
                            Scenario
                          </th>
                          <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3">
                            Score
                          </th>
                          <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 hidden sm:table-cell">
                            Status
                          </th>
                          <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden lg:table-cell">
                            Date
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="session in recentSessions"
                          :key="session.id"
                          class="border-b border-horus-border-subtle last:border-0 hover:bg-horus-bg-tertiary/30 transition-colors cursor-pointer"
                          @click="router.push(`/mission/${session.id}`)"
                        >
                          <td class="px-4 py-3">
                            <p class="text-sm font-medium text-horus-text-primary truncate">
                              {{ session.student_name }}
                            </p>
                          </td>
                          <td class="px-3 py-3 hidden md:table-cell">
                            <p class="text-sm text-horus-text-secondary truncate max-w-[200px]">
                              {{ session.scenario_name }}
                            </p>
                          </td>
                          <td class="px-3 py-3 text-center">
                            <span :class="['text-sm font-bold font-mono', getScoreColor(session.score)]">
                              {{ session.score }}%
                            </span>
                          </td>
                          <td class="px-3 py-3 text-center hidden sm:table-cell">
                            <HBadge :variant="getStatusVariant(session.status)" size="sm">
                              {{ session.status }}
                            </HBadge>
                          </td>
                          <td class="px-4 py-3 text-right hidden lg:table-cell">
                            <span class="text-xs text-horus-text-muted">
                              {{ formatDate(session.started_at) }}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </HCard>
              </HSection>
            </div>

            <!-- Top Performers -->
            <div>
              <HSection title="Top Performers" icon="heroicons:trophy">
                <HCard variant="elevated" padding="md">
                  <div v-if="topStudents.length === 0" class="py-6 text-center">
                    <Icon name="heroicons:users" class="w-8 h-8 text-horus-text-muted mx-auto mb-2" />
                    <p class="text-sm text-horus-text-muted">No student data</p>
                  </div>

                  <div v-else class="space-y-3">
                    <div
                      v-for="(student, idx) in topStudents"
                      :key="student.user_id"
                      class="flex items-center gap-3 p-2 rounded-lg hover:bg-horus-bg-tertiary/50 transition-colors cursor-pointer"
                      @click="handleStudentClick(student.user_id)"
                    >
                      <!-- Rank -->
                      <span
                        :class="[
                          'w-6 text-center text-sm font-bold',
                          idx === 0 ? 'text-yellow-400' : idx < 3 ? 'text-horus-accent-cyan' : 'text-horus-text-muted',
                        ]"
                      >
                        {{ idx + 1 }}
                      </span>

                      <!-- Avatar -->
                      <div class="w-7 h-7 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden flex-shrink-0">
                        <img
                          :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${student.avatar_seed || student.user_id}`"
                          :alt="student.display_name"
                          class="w-full h-full object-cover"
                        />
                      </div>

                      <!-- Name -->
                      <div class="flex-1 min-w-0">
                        <p class="text-sm text-horus-text-primary truncate">{{ student.display_name }}</p>
                      </div>

                      <!-- Score -->
                      <span :class="['text-sm font-bold font-mono', getScoreColor(student.overall_score)]">
                        {{ student.overall_score.toFixed(0) }}%
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

    <template #panel>
      <div class="space-y-6">
        <!-- Period Filter -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:funnel" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">TIME PERIOD</h2>
          </div>
          <div class="space-y-1">
            <button
              v-for="period in [
                { value: 'week', label: 'This Week' },
                { value: 'month', label: 'This Month' },
                { value: 'all', label: 'All Time' },
              ] as const"
              :key="period.value"
              :class="[
                'w-full text-left px-3 py-2 rounded-lg text-sm transition-colors',
                selectedPeriod === period.value
                  ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border border-horus-accent-cyan/20'
                  : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary border border-transparent',
              ]"
              @click="selectedPeriod = period.value"
            >
              {{ period.label }}
            </button>
          </div>
        </div>

        <!-- Quick Stats -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:chart-bar" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">QUICK STATS</h2>
          </div>
          <div v-if="stats" class="space-y-2">
            <div class="flex items-center justify-between p-2 rounded-lg bg-horus-bg-tertiary/50">
              <span class="text-xs text-horus-text-muted">Students</span>
              <span class="text-sm font-bold text-horus-text-primary font-mono">{{ stats.total_students }}</span>
            </div>
            <div class="flex items-center justify-between p-2 rounded-lg bg-horus-bg-tertiary/50">
              <span class="text-xs text-horus-text-muted">Avg Score</span>
              <span class="text-sm font-bold text-horus-text-primary font-mono">{{ stats.average_student_score.toFixed(1) }}%</span>
            </div>
            <div class="flex items-center justify-between p-2 rounded-lg bg-horus-bg-tertiary/50">
              <span class="text-xs text-horus-text-muted">Active Now</span>
              <span class="text-sm font-bold text-horus-status-success font-mono">{{ stats.active_sessions }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
