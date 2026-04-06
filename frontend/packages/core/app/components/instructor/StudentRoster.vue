<script setup lang="ts">
import type { InstructorStudent } from '~/composables/useInstructor'

interface Props {
  students: InstructorStudent[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'student-click': [studentId: string]
}>()

const searchQuery = ref('')
const sortField = ref<'display_name' | 'flight_hours' | 'scenarios_completed' | 'overall_score' | 'last_active'>('display_name')
const sortDirection = ref<'asc' | 'desc'>('asc')
const expandedStudentId = ref<string | null>(null)

const filteredStudents = computed(() => {
  const query = searchQuery.value.toLowerCase().trim()
  return props.students
    .filter(s =>
      !query
      || s.display_name.toLowerCase().includes(query)
      || s.email.toLowerCase().includes(query),
    )
    .sort((a, b) => {
      const dir = sortDirection.value === 'asc' ? 1 : -1
      switch (sortField.value) {
        case 'display_name':
          return dir * a.display_name.localeCompare(b.display_name)
        case 'flight_hours':
          return dir * (a.flight_hours - b.flight_hours)
        case 'scenarios_completed':
          return dir * (a.scenarios_completed - b.scenarios_completed)
        case 'overall_score':
          return dir * (a.overall_score - b.overall_score)
        case 'last_active': {
          const dateA = a.last_active ? new Date(a.last_active).getTime() : 0
          const dateB = b.last_active ? new Date(b.last_active).getTime() : 0
          return dir * (dateA - dateB)
        }
        default:
          return 0
      }
    })
})

function toggleSort(field: typeof sortField.value) {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  }
  else {
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

function toggleExpand(studentId: string) {
  expandedStudentId.value = expandedStudentId.value === studentId ? null : studentId
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatScore(score: number): string {
  return score.toFixed(0)
}

function getScoreVariant(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

function getSortIcon(field: typeof sortField.value): string {
  if (sortField.value !== field) return 'heroicons:chevron-up-down'
  return sortDirection.value === 'asc' ? 'heroicons:chevron-up' : 'heroicons:chevron-down'
}
</script>

<template>
  <div class="space-y-4">
    <!-- Search -->
    <div class="relative max-w-sm">
      <Icon
        name="heroicons:magnifying-glass"
        class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-horus-text-muted"
      />
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search students..."
        class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg pl-10 pr-4 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
      />
    </div>

    <!-- Empty State -->
    <div v-if="filteredStudents.length === 0" class="text-center py-8">
      <Icon name="heroicons:users" class="w-10 h-10 text-horus-text-muted mx-auto mb-2 opacity-50" />
      <p class="text-sm text-horus-text-muted">
        {{ searchQuery ? 'No students match your search' : 'No students found' }}
      </p>
    </div>

    <!-- Table -->
    <HCard v-else variant="elevated" padding="none">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-horus-border-subtle">
              <th class="text-left px-4 py-3">
                <button
                  class="flex items-center gap-1 text-xxs font-semibold uppercase tracking-wider text-horus-text-muted hover:text-horus-text-primary transition-colors"
                  @click="toggleSort('display_name')"
                >
                  Student
                  <Icon :name="getSortIcon('display_name')" class="w-3 h-3" />
                </button>
              </th>
              <th class="text-center px-3 py-3 hidden md:table-cell">
                <button
                  class="flex items-center gap-1 text-xxs font-semibold uppercase tracking-wider text-horus-text-muted hover:text-horus-text-primary transition-colors mx-auto"
                  @click="toggleSort('flight_hours')"
                >
                  Hours
                  <Icon :name="getSortIcon('flight_hours')" class="w-3 h-3" />
                </button>
              </th>
              <th class="text-center px-3 py-3 hidden md:table-cell">
                <button
                  class="flex items-center gap-1 text-xxs font-semibold uppercase tracking-wider text-horus-text-muted hover:text-horus-text-primary transition-colors mx-auto"
                  @click="toggleSort('scenarios_completed')"
                >
                  Scenarios
                  <Icon :name="getSortIcon('scenarios_completed')" class="w-3 h-3" />
                </button>
              </th>
              <th class="text-center px-3 py-3">
                <button
                  class="flex items-center gap-1 text-xxs font-semibold uppercase tracking-wider text-horus-text-muted hover:text-horus-text-primary transition-colors mx-auto"
                  @click="toggleSort('overall_score')"
                >
                  Score
                  <Icon :name="getSortIcon('overall_score')" class="w-3 h-3" />
                </button>
              </th>
              <th class="text-right px-4 py-3 hidden lg:table-cell">
                <button
                  class="flex items-center gap-1 text-xxs font-semibold uppercase tracking-wider text-horus-text-muted hover:text-horus-text-primary transition-colors ml-auto"
                  @click="toggleSort('last_active')"
                >
                  Last Active
                  <Icon :name="getSortIcon('last_active')" class="w-3 h-3" />
                </button>
              </th>
              <th class="w-10 px-2 py-3" />
            </tr>
          </thead>
          <tbody>
            <template v-for="student in filteredStudents" :key="student.user_id">
              <!-- Main Row -->
              <tr
                :class="[
                  'border-b border-horus-border-subtle transition-colors cursor-pointer',
                  expandedStudentId === student.user_id
                    ? 'bg-horus-accent-cyan/5'
                    : 'hover:bg-horus-bg-tertiary/50',
                ]"
                @click="toggleExpand(student.user_id)"
              >
                <!-- Student Name -->
                <td class="px-4 py-3">
                  <div class="flex items-center gap-3 min-w-0">
                    <div class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden flex-shrink-0">
                      <img
                        :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${student.avatar_seed || student.user_id}`"
                        :alt="student.display_name"
                        class="w-full h-full object-cover"
                      />
                    </div>
                    <div class="min-w-0">
                      <p class="text-sm font-medium text-horus-text-primary truncate">
                        {{ student.display_name }}
                      </p>
                      <p class="text-xs text-horus-text-muted truncate">{{ student.email }}</p>
                    </div>
                  </div>
                </td>

                <!-- Flight Hours -->
                <td class="px-3 py-3 text-center hidden md:table-cell">
                  <span class="text-sm text-horus-text-secondary font-mono">
                    {{ student.flight_hours.toFixed(1) }}h
                  </span>
                </td>

                <!-- Scenarios -->
                <td class="px-3 py-3 text-center hidden md:table-cell">
                  <span class="text-sm text-horus-text-secondary">
                    {{ student.scenarios_completed }}
                  </span>
                </td>

                <!-- Score -->
                <td class="px-3 py-3 text-center">
                  <HBadge :variant="getScoreVariant(student.overall_score)" size="sm">
                    {{ formatScore(student.overall_score) }}%
                  </HBadge>
                </td>

                <!-- Last Active -->
                <td class="px-4 py-3 text-right hidden lg:table-cell">
                  <span class="text-xs text-horus-text-muted">
                    {{ formatDate(student.last_active) }}
                  </span>
                </td>

                <!-- Expand Icon -->
                <td class="px-2 py-3">
                  <Icon
                    name="heroicons:chevron-down"
                    :class="[
                      'w-4 h-4 text-horus-text-muted transition-transform duration-200',
                      expandedStudentId === student.user_id && 'rotate-180',
                    ]"
                  />
                </td>
              </tr>

              <!-- Expanded Detail Row -->
              <tr v-if="expandedStudentId === student.user_id">
                <td colspan="6" class="px-4 py-4 bg-horus-bg-secondary/50">
                  <div class="space-y-4 animate-fade-in">
                    <!-- Strengths & Weaknesses -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <p class="text-xxs font-semibold uppercase tracking-wider text-horus-status-success mb-2">
                          Strengths
                        </p>
                        <div class="flex flex-wrap gap-1.5">
                          <span
                            v-for="strength in student.strengths"
                            :key="strength"
                            class="inline-flex items-center px-2 py-0.5 rounded text-xxs font-medium bg-horus-status-success/10 text-horus-status-success border border-horus-status-success/20"
                          >
                            {{ strength }}
                          </span>
                          <span
                            v-if="student.strengths.length === 0"
                            class="text-xs text-horus-text-muted"
                          >
                            No data yet
                          </span>
                        </div>
                      </div>

                      <div>
                        <p class="text-xxs font-semibold uppercase tracking-wider text-horus-status-warning mb-2">
                          Areas for Improvement
                        </p>
                        <div class="flex flex-wrap gap-1.5">
                          <span
                            v-for="weakness in student.weaknesses"
                            :key="weakness"
                            class="inline-flex items-center px-2 py-0.5 rounded text-xxs font-medium bg-horus-status-warning/10 text-horus-status-warning border border-horus-status-warning/20"
                          >
                            {{ weakness }}
                          </span>
                          <span
                            v-if="student.weaknesses.length === 0"
                            class="text-xs text-horus-text-muted"
                          >
                            No data yet
                          </span>
                        </div>
                      </div>
                    </div>

                    <!-- Recent Sessions -->
                    <div v-if="student.recent_sessions.length > 0">
                      <p class="text-xxs font-semibold uppercase tracking-wider text-horus-text-secondary mb-2">
                        Recent Sessions
                      </p>
                      <div class="space-y-1.5">
                        <div
                          v-for="session in student.recent_sessions.slice(0, 3)"
                          :key="session.id"
                          class="flex items-center justify-between p-2 rounded-lg bg-horus-bg-tertiary/50"
                        >
                          <div class="flex items-center gap-2 min-w-0">
                            <Icon name="heroicons:play-circle" class="w-4 h-4 text-horus-text-muted flex-shrink-0" />
                            <span class="text-xs text-horus-text-primary truncate">{{ session.scenario_name }}</span>
                          </div>
                          <div class="flex items-center gap-3 flex-shrink-0">
                            <HBadge :variant="getScoreVariant(session.score)" size="sm">
                              {{ session.score }}%
                            </HBadge>
                            <span class="text-xxs text-horus-text-muted">{{ session.duration_minutes }}m</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Action Button -->
                    <div class="flex justify-end">
                      <HButton
                        variant="secondary"
                        size="sm"
                        icon="heroicons:arrow-top-right-on-square"
                        @click.stop="emit('student-click', student.user_id)"
                      >
                        View Full Profile
                      </HButton>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </HCard>

    <!-- Count -->
    <p class="text-xs text-horus-text-muted">
      Showing {{ filteredStudents.length }} of {{ students.length }} students
    </p>
  </div>
</template>
