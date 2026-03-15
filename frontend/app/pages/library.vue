<script setup lang="ts">
definePageMeta({
  layout: 'default',
  middleware: 'auth',
})

interface Scenario {
  id: number
  name: string
  description: string | null
  difficulty: number
  airport_icao: string
  runway: string
  weather_preset: string
  phase: string
  created_at: string
}

const api = useApi()
const router = useRouter()

const scenarios = ref<Scenario[]>([])
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const filterPhase = ref('')
const filterDifficulty = ref('')

async function fetchScenarios() {
  isLoading.value = true
  errorMessage.value = null
  try {
    scenarios.value = await api.get<Scenario[]>('/api/v1/scenarios')
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load scenarios'
  }
  finally {
    isLoading.value = false
  }
}

const filteredScenarios = computed(() => {
  return scenarios.value.filter((s) => {
    if (filterPhase.value && filterPhase.value !== 'all' && s.phase !== filterPhase.value) return false
    if (filterDifficulty.value && filterDifficulty.value !== 'all') {
      const level = Number(filterDifficulty.value)
      if (s.difficulty !== level) return false
    }
    return true
  })
})

function getDifficultyLabel(level: number): string {
  if (level >= 4) return 'Expert'
  if (level >= 2) return 'Proficient'
  return 'Novice'
}

function getDifficultyVariant(level: number): 'danger' | 'warning' | 'active' {
  if (level >= 4) return 'danger'
  if (level >= 2) return 'warning'
  return 'active'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function handlePreview(scenario: Scenario) {
  router.push(`/configurator?scenario=${scenario.id}`)
}

async function handleRun(scenario: Scenario) {
  try {
    const session = await api.post<{ id: number }>('/api/v1/sessions', {
      scenario_id: scenario.id,
      language: 'en',
    })
    router.push(`/mission/${session.id}`)
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to start session'
  }
}

async function handleCreateScenario() {
  // Navigate to configurator for scenario creation
  router.push('/configurator')
}

onMounted(() => {
  fetchScenarios()
})
</script>

<template>
  <NuxtLayout>
    <template #sidebar>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:funnel" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">FILTERS</h2>
        </div>

        <div class="space-y-3">
          <HDropdown
            v-model="filterPhase"
            :options="[
              { value: 'all', label: 'All Phases' },
              { value: 'ground', label: 'Ground' },
              { value: 'departure', label: 'Departure' },
              { value: 'enroute', label: 'Enroute' },
              { value: 'approach', label: 'Approach' }
            ]"
            label="Scenario Phase"
            placeholder="Select phase"
          />

          <HDropdown
            v-model="filterDifficulty"
            :options="[
              { value: 'all', label: 'All Levels' },
              { value: '1', label: 'Novice (1)' },
              { value: '2', label: 'Proficient (2-3)' },
              { value: '4', label: 'Expert (4-5)' }
            ]"
            label="Difficulty"
            placeholder="Select difficulty"
          />
        </div>
      </div>
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <div class="flex items-center justify-between">
          <h1 class="text-xl font-semibold text-horus-text-primary">Scenario Library</h1>
          <HButton variant="primary" size="sm" icon="heroicons:plus" @click="handleCreateScenario">
            New Scenario
          </HButton>
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
        <div v-if="isLoading" class="flex items-center justify-center py-16">
          <div class="text-center space-y-3">
            <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
            <p class="text-sm text-horus-text-muted">Loading scenarios...</p>
          </div>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="filteredScenarios.length === 0 && !errorMessage"
          class="flex flex-col items-center justify-center py-16 text-center"
        >
          <Icon name="heroicons:book-open" class="w-12 h-12 text-horus-text-muted mb-4 opacity-50" />
          <p class="text-sm text-horus-text-secondary mb-1">No scenarios found</p>
          <p class="text-xs text-horus-text-muted">
            {{ scenarios.length > 0 ? 'Try adjusting your filters' : 'Create your first scenario to get started' }}
          </p>
        </div>

        <!-- Scenarios Grid -->
        <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <HCard
            v-for="scenario in filteredScenarios"
            :key="scenario.id"
            variant="default"
            padding="md"
            hover
            class="cursor-pointer"
          >
            <div class="space-y-3">
              <div class="flex items-start justify-between">
                <h3 class="text-sm font-semibold text-horus-text-primary">{{ scenario.name }}</h3>
                <HBadge :variant="getDifficultyVariant(scenario.difficulty)" size="sm">
                  {{ getDifficultyLabel(scenario.difficulty) }}
                </HBadge>
              </div>

              <p v-if="scenario.description" class="text-xs text-horus-text-secondary line-clamp-2">
                {{ scenario.description }}
              </p>

              <div class="flex items-center gap-4 text-xs text-horus-text-muted">
                <span class="flex items-center gap-1">
                  <Icon name="heroicons:map-pin" class="w-3 h-3" />
                  {{ scenario.airport_icao }} / {{ scenario.runway }}
                </span>
                <span class="flex items-center gap-1">
                  <Icon name="heroicons:cloud" class="w-3 h-3" />
                  {{ scenario.weather_preset }}
                </span>
                <span class="flex items-center gap-1">
                  <Icon name="heroicons:calendar" class="w-3 h-3" />
                  {{ formatDate(scenario.created_at) }}
                </span>
              </div>

              <div class="flex gap-2 pt-2">
                <HButton variant="ghost" size="sm" class="flex-1" @click="handlePreview(scenario)">
                  <Icon name="heroicons:eye" class="w-4 h-4" />
                  Preview
                </HButton>
                <HButton variant="secondary" size="sm" class="flex-1" @click="handleRun(scenario)">
                  <Icon name="heroicons:play" class="w-4 h-4" />
                  Run
                </HButton>
              </div>
            </div>
          </HCard>
        </div>
      </div>
    </template>

    <template #panel>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">QUICK STATS</h2>
        </div>

        <div class="space-y-3">
          <HDataPanel
            :value="String(scenarios.length)"
            label="Total Scenarios"
            variant="compact"
          />
          <HDataPanel
            :value="String(scenarios.filter(s => s.weather_preset === 'IFR' || s.weather_preset === 'LIFR').length)"
            label="IFR / LIFR"
            variant="compact"
          />
          <HDataPanel
            :value="String(scenarios.filter(s => s.difficulty >= 4).length)"
            label="Expert Level"
            variant="compact"
          />
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
