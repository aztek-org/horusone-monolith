<script setup lang="ts">
import type {
  Assessment,
  AssessmentDetail,
  AssessmentResult,
  AnswerEntry,
} from '~/composables/useAssessments'

definePageMeta({
  layout: false,
  middleware: 'auth',
})

const assessmentsApi = useAssessments()
const route = useRoute()
const router = useRouter()

// --- View State ---

type ViewMode = 'list' | 'taking' | 'results'

const viewMode = ref<ViewMode>('list')

// --- List View State ---

const assessments = ref<Assessment[]>([])
const isLoadingList = ref(true)
const errorMessage = ref<string | null>(null)
const moduleFilter = ref('all')

// --- Taking View State ---

const activeAssessment = ref<AssessmentDetail | null>(null)
const isLoadingAssessment = ref(false)
const currentQuestionIndex = ref(0)
const answers = ref<Map<number, string>>(new Map())
const startTime = ref<number>(0)
const elapsedSeconds = ref(0)
const timerInterval = ref<ReturnType<typeof setInterval> | null>(null)
const isSubmitting = ref(false)

// --- Results View State ---

const currentResult = ref<AssessmentResult | null>(null)

// --- Computed ---

const filteredAssessments = computed(() => {
  if (moduleFilter.value === 'all') return assessments.value
  return assessments.value.filter(a => a.module === moduleFilter.value)
})

const availableModules = computed(() => {
  const modules = new Set(assessments.value.map(a => a.module))
  return ['all', ...Array.from(modules)]
})

const currentQuestion = computed(() => {
  if (!activeAssessment.value) return null
  return activeAssessment.value.questions[currentQuestionIndex.value] ?? null
})

const totalQuestions = computed(() =>
  activeAssessment.value?.questions.length ?? 0,
)

const answeredCount = computed(() => answers.value.size)

const progressPercent = computed(() => {
  if (totalQuestions.value === 0) return 0
  return Math.round((answeredCount.value / totalQuestions.value) * 100)
})

const selectedOption = computed(() => {
  if (!currentQuestion.value) return null
  return answers.value.get(currentQuestion.value.id) ?? null
})

const canSubmit = computed(() =>
  answeredCount.value === totalQuestions.value,
)

const timeLimitExceeded = computed(() => {
  if (!activeAssessment.value?.timeLimitMinutes) return false
  return elapsedSeconds.value >= activeAssessment.value.timeLimitMinutes * 60
})

const formattedTime = computed(() => {
  const mins = Math.floor(elapsedSeconds.value / 60)
  const secs = elapsedSeconds.value % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
})

const remainingTime = computed(() => {
  if (!activeAssessment.value?.timeLimitMinutes) return null
  const remaining = activeAssessment.value.timeLimitMinutes * 60 - elapsedSeconds.value
  if (remaining <= 0) return '00:00'
  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
})

// --- Data Fetching ---

async function fetchAssessments() {
  isLoadingList.value = true
  errorMessage.value = null
  try {
    assessments.value = await assessmentsApi.listAssessments()
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load assessments'
  }
  finally {
    isLoadingList.value = false
  }
}

async function startAssessment(id: number) {
  isLoadingAssessment.value = true
  errorMessage.value = null

  try {
    activeAssessment.value = await assessmentsApi.getAssessment(id)
    answers.value = new Map()
    currentQuestionIndex.value = 0
    startTime.value = Date.now()
    elapsedSeconds.value = 0
    viewMode.value = 'taking'

    // Start timer
    timerInterval.value = setInterval(() => {
      elapsedSeconds.value = Math.floor((Date.now() - startTime.value) / 1000)

      // Auto-submit if time limit exceeded
      if (timeLimitExceeded.value) {
        handleSubmit()
      }
    }, 1000)
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load assessment'
  }
  finally {
    isLoadingAssessment.value = false
  }
}

function selectAnswer(optionId: string) {
  if (!currentQuestion.value) return
  answers.value.set(currentQuestion.value.id, optionId)
}

function goToQuestion(index: number) {
  if (index >= 0 && index < totalQuestions.value) {
    currentQuestionIndex.value = index
  }
}

function nextQuestion() {
  goToQuestion(currentQuestionIndex.value + 1)
}

function prevQuestion() {
  goToQuestion(currentQuestionIndex.value - 1)
}

async function handleSubmit() {
  if (!activeAssessment.value || isSubmitting.value) return

  isSubmitting.value = true
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
    timerInterval.value = null
  }

  try {
    const answerEntries: AnswerEntry[] = []
    for (const [questionId, selectedOptionId] of answers.value) {
      answerEntries.push({ questionId, selectedOptionId })
    }

    currentResult.value = await assessmentsApi.submitAssessment(
      activeAssessment.value.id,
      {
        assessmentId: activeAssessment.value.id,
        answers: answerEntries,
        timeTakenSeconds: elapsedSeconds.value,
      },
    )
    viewMode.value = 'results'
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to submit assessment'
  }
  finally {
    isSubmitting.value = false
  }
}

function backToList() {
  viewMode.value = 'list'
  activeAssessment.value = null
  currentResult.value = null
  answers.value = new Map()
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
    timerInterval.value = null
  }
}

function retakeAssessment() {
  if (currentResult.value) {
    startAssessment(currentResult.value.assessmentId)
  }
}

// --- Helpers ---

function getDifficultyVariant(d: string): 'active' | 'warning' | 'danger' {
  switch (d) {
    case 'advanced': return 'danger'
    case 'intermediate': return 'warning'
    default: return 'active'
  }
}

function getDifficultyLabel(d: string): string {
  switch (d) {
    case 'advanced': return 'Advanced'
    case 'intermediate': return 'Intermediate'
    default: return 'Beginner'
  }
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

// Check for retake query param
onMounted(() => {
  fetchAssessments()

  const retakeId = route.query.retake
  if (retakeId) {
    startAssessment(Number(retakeId))
  }
})

onUnmounted(() => {
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
  }
})
</script>

<template>
  <NuxtLayout>
    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <!-- ===== ASSESSMENT LIST VIEW ===== -->
        <template v-if="viewMode === 'list'">
          <!-- Header -->
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 class="text-xl font-semibold text-horus-text-primary">
                Assessments
              </h1>
              <p class="text-sm text-horus-text-secondary mt-1">
                Test your aviation knowledge and track your progress
              </p>
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

          <!-- Module Filters -->
          <div class="flex items-center gap-2 flex-wrap">
            <button
              v-for="mod in availableModules"
              :key="mod"
              :class="[
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                moduleFilter === mod
                  ? 'bg-horus-accent-cyan/20 text-horus-accent-cyan border border-horus-accent-cyan/30'
                  : 'bg-horus-bg-tertiary text-horus-text-secondary border border-horus-border-subtle hover:border-horus-accent-cyan/30'
              ]"
              @click="moduleFilter = mod"
            >
              {{ mod === 'all' ? 'All Modules' : mod }}
            </button>
          </div>

          <!-- Loading State -->
          <div v-if="isLoadingList" class="flex items-center justify-center py-16">
            <div class="text-center space-y-3">
              <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
              <p class="text-sm text-horus-text-muted">Loading assessments...</p>
            </div>
          </div>

          <!-- Empty State -->
          <div
            v-else-if="filteredAssessments.length === 0"
            class="text-center py-16"
          >
            <Icon name="heroicons:clipboard-document-check" class="w-12 h-12 text-horus-text-muted mx-auto mb-4 opacity-50" />
            <p class="text-sm text-horus-text-secondary">
              {{ assessments.length > 0 ? 'No assessments match your filter' : 'No assessments available yet' }}
            </p>
          </div>

          <!-- Assessment Grid -->
          <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <HCard
              v-for="assessment in filteredAssessments"
              :key="assessment.id"
              variant="default"
              padding="md"
              hover
            >
              <div class="space-y-3">
                <!-- Title & Difficulty -->
                <div class="flex items-start justify-between gap-2">
                  <h3 class="text-sm font-semibold text-horus-text-primary">
                    {{ assessment.title }}
                  </h3>
                  <HBadge :variant="getDifficultyVariant(assessment.difficulty)" size="sm" class="flex-shrink-0">
                    {{ getDifficultyLabel(assessment.difficulty) }}
                  </HBadge>
                </div>

                <!-- Description -->
                <p class="text-xs text-horus-text-secondary line-clamp-2">
                  {{ assessment.description }}
                </p>

                <!-- Meta -->
                <div class="flex items-center gap-3 text-xxs text-horus-text-muted">
                  <span class="flex items-center gap-1">
                    <Icon name="heroicons:queue-list" class="w-3 h-3" />
                    {{ assessment.questionCount }} questions
                  </span>
                  <span class="flex items-center gap-1">
                    <Icon name="heroicons:check-badge" class="w-3 h-3" />
                    {{ assessment.passingScore }}% to pass
                  </span>
                  <span v-if="assessment.timeLimitMinutes" class="flex items-center gap-1">
                    <Icon name="heroicons:clock" class="w-3 h-3" />
                    {{ assessment.timeLimitMinutes }}min
                  </span>
                </div>

                <!-- Module Badge -->
                <HBadge variant="info" size="sm">
                  {{ assessment.module }}
                </HBadge>

                <!-- Start Button -->
                <HButton
                  variant="primary"
                  size="sm"
                  icon="heroicons:play"
                  class="w-full"
                  :loading="isLoadingAssessment"
                  @click="startAssessment(assessment.id)"
                >
                  Start Assessment
                </HButton>
              </div>
            </HCard>
          </div>
        </template>

        <!-- ===== ASSESSMENT TAKING VIEW ===== -->
        <template v-else-if="viewMode === 'taking' && activeAssessment && currentQuestion">
          <!-- Header Bar -->
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div class="flex items-center gap-3">
              <button
                class="p-1.5 rounded-lg hover:bg-horus-bg-tertiary transition-colors"
                @click="backToList"
              >
                <Icon name="heroicons:x-mark" class="w-5 h-5 text-horus-text-secondary" />
              </button>
              <div>
                <h1 class="text-lg font-semibold text-horus-text-primary">
                  {{ activeAssessment.title }}
                </h1>
                <p class="text-xxs text-horus-text-muted">
                  Question {{ currentQuestionIndex + 1 }} of {{ totalQuestions }}
                </p>
              </div>
            </div>

            <!-- Timer -->
            <div class="flex items-center gap-3">
              <div
                v-if="activeAssessment.timeLimitMinutes"
                :class="[
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono text-sm',
                  timeLimitExceeded
                    ? 'bg-horus-status-danger/10 text-horus-status-danger border border-horus-status-danger/30'
                    : 'bg-horus-bg-tertiary text-horus-text-primary border border-horus-border-subtle'
                ]"
              >
                <Icon name="heroicons:clock" class="w-4 h-4" />
                {{ remainingTime }}
              </div>
              <div
                v-else
                class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-horus-bg-tertiary text-horus-text-secondary border border-horus-border-subtle font-mono text-sm"
              >
                <Icon name="heroicons:clock" class="w-4 h-4" />
                {{ formattedTime }}
              </div>
            </div>
          </div>

          <!-- Progress Bar -->
          <HProgress
            :value="answeredCount"
            :max="totalQuestions"
            :label="`${answeredCount} of ${totalQuestions} answered`"
            size="sm"
          />

          <!-- Question Card -->
          <HCard variant="elevated" padding="lg">
            <div class="space-y-6">
              <!-- Question Text -->
              <div class="space-y-2">
                <span class="text-xxs text-horus-accent-cyan uppercase tracking-wider font-semibold">
                  Question {{ currentQuestionIndex + 1 }}
                </span>
                <h2 class="text-lg font-semibold text-horus-text-primary leading-relaxed">
                  {{ currentQuestion.text }}
                </h2>
              </div>

              <!-- Options -->
              <div class="space-y-3">
                <button
                  v-for="(option, idx) in currentQuestion.options"
                  :key="option.id"
                  :class="[
                    'w-full flex items-start gap-4 p-4 rounded-lg border text-left transition-all duration-200',
                    selectedOption === option.id
                      ? 'bg-horus-accent-cyan/10 border-horus-accent-cyan/50 shadow-glow-cyan/10'
                      : 'bg-horus-bg-secondary border-horus-border-subtle hover:border-horus-accent-cyan/30 hover:bg-horus-bg-tertiary'
                  ]"
                  @click="selectAnswer(option.id)"
                >
                  <!-- Option Letter -->
                  <span
                    :class="[
                      'w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0',
                      selectedOption === option.id
                        ? 'bg-horus-accent-cyan text-horus-bg-primary'
                        : 'bg-horus-bg-tertiary text-horus-text-secondary'
                    ]"
                  >
                    {{ String.fromCharCode(65 + idx) }}
                  </span>

                  <!-- Option Text -->
                  <span
                    :class="[
                      'text-sm pt-1',
                      selectedOption === option.id
                        ? 'text-horus-text-primary'
                        : 'text-horus-text-secondary'
                    ]"
                  >
                    {{ option.text }}
                  </span>
                </button>
              </div>
            </div>
          </HCard>

          <!-- Navigation -->
          <div class="flex items-center justify-between">
            <HButton
              variant="ghost"
              size="md"
              :disabled="currentQuestionIndex === 0"
              @click="prevQuestion"
            >
              <Icon name="heroicons:chevron-left" class="w-4 h-4" />
              Previous
            </HButton>

            <div class="flex items-center gap-1">
              <button
                v-for="(q, idx) in activeAssessment.questions"
                :key="q.id"
                :class="[
                  'w-8 h-8 rounded-md text-xs font-mono font-medium transition-colors',
                  idx === currentQuestionIndex
                    ? 'bg-horus-accent-cyan text-horus-bg-primary'
                    : answers.has(q.id)
                      ? 'bg-horus-status-success/20 text-horus-status-success border border-horus-status-success/30'
                      : 'bg-horus-bg-tertiary text-horus-text-muted border border-horus-border-subtle'
                ]"
                @click="goToQuestion(idx)"
              >
                {{ idx + 1 }}
              </button>
            </div>

            <template v-if="currentQuestionIndex < totalQuestions - 1">
              <HButton
                variant="ghost"
                size="md"
                @click="nextQuestion"
              >
                Next
                <Icon name="heroicons:chevron-right" class="w-4 h-4" />
              </HButton>
            </template>
            <template v-else>
              <HButton
                variant="primary"
                size="md"
                icon="heroicons:paper-airplane"
                :disabled="!canSubmit"
                :loading="isSubmitting"
                @click="handleSubmit"
              >
                Submit
              </HButton>
            </template>
          </div>
        </template>

        <!-- ===== RESULTS VIEW ===== -->
        <template v-else-if="viewMode === 'results' && currentResult">
          <!-- Header -->
          <div class="text-center space-y-2">
            <div
              :class="[
                'inline-flex w-20 h-20 rounded-full items-center justify-center mx-auto',
                currentResult.passed
                  ? 'bg-horus-status-success/20 border-2 border-horus-status-success/50'
                  : 'bg-horus-status-danger/20 border-2 border-horus-status-danger/50'
              ]"
            >
              <Icon
                :name="currentResult.passed ? 'heroicons:check-circle' : 'heroicons:x-circle'"
                :class="[
                  'w-10 h-10',
                  currentResult.passed ? 'text-horus-status-success' : 'text-horus-status-danger'
                ]"
              />
            </div>
            <h1 class="text-2xl font-bold text-horus-text-primary">
              {{ currentResult.passed ? 'Assessment Passed!' : 'Assessment Failed' }}
            </h1>
            <p class="text-sm text-horus-text-secondary">
              {{ currentResult.assessmentTitle }}
            </p>
          </div>

          <!-- Score Card -->
          <HCard variant="elevated" padding="lg">
            <div class="grid gap-6 sm:grid-cols-3 text-center">
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider mb-1">Score</p>
                <span
                  :class="[
                    'text-3xl font-bold font-mono',
                    getScoreColor(currentResult.score, currentResult.maxScore)
                  ]"
                >
                  {{ currentResult.score }}/{{ currentResult.maxScore }}
                </span>
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider mb-1">Correct Answers</p>
                <span class="text-3xl font-bold font-mono text-horus-text-primary">
                  {{ currentResult.questionsCorrect }}/{{ currentResult.questionsTotal }}
                </span>
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider mb-1">Time Taken</p>
                <span class="text-3xl font-bold font-mono text-horus-text-primary">
                  {{ formatDuration(currentResult.timeTakenSeconds) }}
                </span>
              </div>
            </div>

            <div class="mt-6">
              <HProgress
                :value="currentResult.score"
                :max="currentResult.maxScore"
                :variant="currentResult.passed ? 'success' : 'danger'"
                :label="`${currentResult.passingScore}% needed to pass`"
              />
            </div>
          </HCard>

          <!-- Question Breakdown -->
          <HSection icon="heroicons:queue-list" title="Question Breakdown">
            <div class="space-y-3">
              <HCard
                v-for="(answer, idx) in currentResult.answers"
                :key="answer.questionId"
                variant="default"
                padding="md"
              >
                <div class="space-y-3">
                  <!-- Question Header -->
                  <div class="flex items-start gap-3">
                    <span
                      :class="[
                        'w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold flex-shrink-0',
                        answer.isCorrect
                          ? 'bg-horus-status-success/20 text-horus-status-success'
                          : 'bg-horus-status-danger/20 text-horus-status-danger'
                      ]"
                    >
                      {{ idx + 1 }}
                    </span>
                    <p class="text-sm text-horus-text-primary">
                      {{ answer.questionText }}
                    </p>
                  </div>

                  <!-- Your Answer -->
                  <div class="ml-10 space-y-2">
                    <div
                      :class="[
                        'flex items-center gap-2 p-2.5 rounded-lg text-sm',
                        answer.isCorrect
                          ? 'bg-horus-status-success/10 border border-horus-status-success/30'
                          : 'bg-horus-status-danger/10 border border-horus-status-danger/30'
                      ]"
                    >
                      <Icon
                        :name="answer.isCorrect ? 'heroicons:check-circle' : 'heroicons:x-circle'"
                        :class="[
                          'w-4 h-4 flex-shrink-0',
                          answer.isCorrect ? 'text-horus-status-success' : 'text-horus-status-danger'
                        ]"
                      />
                      <span :class="answer.isCorrect ? 'text-horus-status-success' : 'text-horus-status-danger'">
                        {{ answer.selectedOptionText }}
                      </span>
                    </div>

                    <!-- Correct Answer (if wrong) -->
                    <div
                      v-if="!answer.isCorrect"
                      class="flex items-center gap-2 p-2.5 rounded-lg text-sm bg-horus-status-success/10 border border-horus-status-success/30"
                    >
                      <Icon name="heroicons:check-circle" class="w-4 h-4 text-horus-status-success flex-shrink-0" />
                      <span class="text-horus-status-success">
                        {{ answer.correctOptionText }}
                      </span>
                    </div>

                    <!-- Explanation -->
                    <p
                      v-if="answer.explanation"
                      class="text-xs text-horus-text-muted italic pl-1"
                    >
                      💡 {{ answer.explanation }}
                    </p>
                  </div>
                </div>
              </HCard>
            </div>
          </HSection>

          <!-- Actions -->
          <div class="flex items-center justify-center gap-4 pt-4">
            <HButton
              variant="secondary"
              size="md"
              icon="heroicons:arrow-left"
              @click="backToList"
            >
              Back to Assessments
            </HButton>
            <HButton
              variant="primary"
              size="md"
              icon="heroicons:arrow-path"
              @click="retakeAssessment"
            >
              Retake Assessment
            </HButton>
          </div>
        </template>
      </div>
    </template>

    <!-- Right Panel -->
    <template #panel>
      <div class="space-y-6">
        <!-- Assessment Info (List view) -->
        <template v-if="viewMode === 'list'">
          <div class="space-y-3">
            <div class="flex items-center gap-2">
              <Icon name="heroicons:clipboard-document-check" class="w-5 h-5 text-horus-accent-cyan" />
              <h2 class="text-sm font-semibold text-horus-text-primary">OVERVIEW</h2>
            </div>

            <div class="space-y-3">
              <HDataPanel
                :value="String(assessments.length)"
                label="Total Assessments"
                variant="compact"
              />
              <HDataPanel
                :value="String(availableModules.length - 1)"
                label="Modules"
                variant="compact"
              />
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex items-center gap-2">
              <Icon name="heroicons:bolt" class="w-5 h-5 text-horus-accent-cyan" />
              <h2 class="text-sm font-semibold text-horus-text-primary">QUICK LINKS</h2>
            </div>

            <div class="space-y-2">
              <HButton
                variant="secondary"
                size="sm"
                icon="heroicons:chart-bar"
                class="w-full justify-start"
                @click="router.push('/stats')"
              >
                View Stats
              </HButton>
              <HButton
                variant="secondary"
                size="sm"
                icon="heroicons:book-open"
                class="w-full justify-start"
                @click="router.push('/knowledge')"
              >
                Study Materials
              </HButton>
            </div>
          </div>
        </template>

        <!-- Question Nav (Taking view) -->
        <template v-if="viewMode === 'taking' && activeAssessment">
          <div class="space-y-3">
            <div class="flex items-center gap-2">
              <Icon name="heroicons:queue-list" class="w-5 h-5 text-horus-accent-cyan" />
              <h2 class="text-sm font-semibold text-horus-text-primary">QUESTIONS</h2>
            </div>

            <div class="grid grid-cols-5 gap-1.5">
              <button
                v-for="(q, idx) in activeAssessment.questions"
                :key="q.id"
                :class="[
                  'w-full aspect-square rounded-md text-xs font-mono font-medium transition-colors flex items-center justify-center',
                  idx === currentQuestionIndex
                    ? 'bg-horus-accent-cyan text-horus-bg-primary'
                    : answers.has(q.id)
                      ? 'bg-horus-status-success/20 text-horus-status-success border border-horus-status-success/30'
                      : 'bg-horus-bg-tertiary text-horus-text-muted border border-horus-border-subtle'
                ]"
                @click="goToQuestion(idx)"
              >
                {{ idx + 1 }}
              </button>
            </div>

            <div class="pt-3 border-t border-horus-border-subtle space-y-2">
              <HDataPanel
                :value="`${answeredCount}/${totalQuestions}`"
                label="Answered"
                variant="compact"
              />
              <HDataPanel
                :value="formattedTime"
                label="Elapsed Time"
                variant="compact"
              />
            </div>
          </div>

          <div class="pt-4">
            <HButton
              variant="primary"
              size="sm"
              icon="heroicons:paper-airplane"
              class="w-full"
              :disabled="!canSubmit"
              :loading="isSubmitting"
              @click="handleSubmit"
            >
              Submit Assessment
            </HButton>
          </div>
        </template>

        <!-- Result Summary (Results view) -->
        <template v-if="viewMode === 'results' && currentResult">
          <div class="space-y-3">
            <div class="flex items-center gap-2">
              <Icon name="heroicons:trophy" class="w-5 h-5 text-horus-accent-cyan" />
              <h2 class="text-sm font-semibold text-horus-text-primary">RESULT SUMMARY</h2>
            </div>

            <HCard variant="glass" padding="md">
              <div class="text-center space-y-2">
                <HBadge
                  :variant="currentResult.passed ? 'active' : 'danger'"
                  size="md"
                >
                  {{ currentResult.passed ? 'PASSED' : 'FAILED' }}
                </HBadge>
                <p
                  :class="[
                    'text-3xl font-bold font-mono',
                    getScoreColor(currentResult.score, currentResult.maxScore)
                  ]"
                >
                  {{ Math.round((currentResult.score / currentResult.maxScore) * 100) }}%
                </p>
                <p class="text-xxs text-horus-text-muted">
                  {{ currentResult.questionsCorrect }} of {{ currentResult.questionsTotal }} correct
                </p>
              </div>
            </HCard>
          </div>
        </template>
      </div>
    </template>
  </NuxtLayout>
</template>
