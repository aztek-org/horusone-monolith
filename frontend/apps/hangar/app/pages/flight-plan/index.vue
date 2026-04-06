<script setup lang="ts">
import type { FlightPlanCreateData, ValidationResult } from '~/composables/useFlightPlans'

definePageMeta({
  layout: false,
  middleware: 'auth',
})

const router = useRouter()
const {
  flightPlans,
  currentPlan,
  isLoading,
  isSaving,
  isValidating,
  errorMessage,
  validationResponse,
  listFlightPlans,
  createFlightPlan,
  validateFlightPlan,
  activateFlightPlan,
  createFromText,
  createFromImage,
  clearValidation,
} = useFlightPlans()

// Input mode
type InputMode = 'form' | 'text' | 'image'
const activeMode = ref<InputMode>('form')

// Sidebar visibility
const isSidebarVisible = ref(true)

// Form state
const formData = reactive<FlightPlanCreateData>({
  title: '',
  aircraft_type: 'C172',
  departure_icao: '',
  arrival_icao: '',
  alternate_icao: '',
  route_string: '',
  cruise_altitude_ft: undefined,
  fuel_required_lbs: undefined,
  fuel_reserve_lbs: undefined,
  total_fuel_lbs: undefined,
  total_weight_lbs: undefined,
  max_weight_lbs: undefined,
  cg_position: undefined,
})

// Text mode state
const textInput = ref('')
const isParsingText = ref(false)

// Image mode state
const imageFile = ref<File | null>(null)
const imagePreview = ref<string | null>(null)
const isParsingImage = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// Aircraft options
const aircraftOptions = [
  { value: 'C172', label: 'Cessna 172 Skyhawk' },
  { value: 'C182', label: 'Cessna 182 Skylane' },
  { value: 'PA28', label: 'Piper PA-28 Cherokee' },
  { value: 'B738', label: 'Boeing 737-800' },
  { value: 'A320', label: 'Airbus A320' },
]

// Max weights by aircraft
const maxWeights: Record<string, number> = {
  C172: 2550,
  C182: 3100,
  PA28: 2440,
  B738: 174200,
  A320: 170000,
}

// Auto-compute max weight
watch(() => formData.aircraft_type, (newType) => {
  formData.max_weight_lbs = maxWeights[newType] ?? undefined
})

// Auto-compute total fuel
watch(
  () => [formData.fuel_required_lbs, formData.fuel_reserve_lbs],
  () => {
    const req = formData.fuel_required_lbs ?? 0
    const res = formData.fuel_reserve_lbs ?? 0
    if (req > 0 || res > 0) {
      formData.total_fuel_lbs = req + res
    }
  },
  { deep: true },
)

// CG within limits check
const cgWithinLimits = computed(() => {
  if (formData.total_weight_lbs === undefined || formData.max_weight_lbs === undefined) return null
  return formData.total_weight_lbs <= formData.max_weight_lbs
})

// Computed: map coordinates (mock for now — would come from airport DB)
const airportCoords: Record<string, { lat: number; lon: number }> = {
  KJFK: { lat: 40.6413, lon: -73.7781 },
  KLAX: { lat: 33.9425, lon: -118.4081 },
  KORD: { lat: 41.9742, lon: -87.9073 },
  KATL: { lat: 33.6407, lon: -84.4277 },
  KSFO: { lat: 37.6213, lon: -122.3790 },
  KDEN: { lat: 39.8561, lon: -104.6737 },
  KDFW: { lat: 32.8998, lon: -97.0403 },
  KMIA: { lat: 25.7959, lon: -80.2870 },
  KBOS: { lat: 42.3656, lon: -71.0096 },
  KSEA: { lat: 47.4502, lon: -122.3088 },
  MMGL: { lat: 20.5218, lon: -103.3111 },
  MMMX: { lat: 19.4363, lon: -99.0721 },
  EGLL: { lat: 51.4700, lon: -0.4543 },
  LFPG: { lat: 49.0097, lon: 2.5479 },
}

const depCoords = computed(() => {
  const icao = formData.departure_icao.toUpperCase()
  return airportCoords[icao] ?? null
})

const arrCoords = computed(() => {
  const icao = formData.arrival_icao.toUpperCase()
  return airportCoords[icao] ?? null
})

// Validation results as flat array
const validationResults = computed<ValidationResult[]>(() => {
  return validationResponse.value?.results ?? []
})

// Can activate
const canActivate = computed(() => {
  return validationResponse.value?.is_valid === true && currentPlan.value?.status === 'validated'
})

// Status badge variant
function statusVariant(status: string): 'active' | 'warning' | 'info' | 'idle' | 'success' {
  switch (status) {
    case 'draft': return 'idle'
    case 'validated': return 'info'
    case 'active': return 'active'
    case 'completed': return 'success'
    default: return 'idle'
  }
}

// Handlers
async function handleSaveDraft() {
  clearValidation()
  if (currentPlan.value) {
    // Update existing
    const { updateFlightPlan } = useFlightPlans()
    await updateFlightPlan(currentPlan.value.id, { ...formData })
  }
  else {
    // Create new
    await createFlightPlan({ ...formData })
  }
}

async function handleValidate() {
  if (!currentPlan.value) {
    // Save first
    await handleSaveDraft()
  }
  if (currentPlan.value) {
    await validateFlightPlan(currentPlan.value.id)
  }
}

async function handleActivate() {
  if (currentPlan.value) {
    await activateFlightPlan(currentPlan.value.id)
  }
}

async function handleParseText() {
  if (!textInput.value.trim()) return
  isParsingText.value = true
  const plan = await createFromText(textInput.value)
  isParsingText.value = false
  if (plan) {
    populateFormFromPlan(plan)
    activeMode.value = 'form'
  }
}

function handleImageSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  setImageFile(file)
}

function handleImageDrop(event: DragEvent) {
  event.preventDefault()
  const file = event.dataTransfer?.files[0]
  if (!file) return
  setImageFile(file)
}

function setImageFile(file: File) {
  imageFile.value = file
  // Create preview
  const reader = new FileReader()
  reader.onload = (e) => {
    imagePreview.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
}

async function handleExtractImage() {
  if (!imageFile.value) return
  isParsingImage.value = true
  const plan = await createFromImage(imageFile.value)
  isParsingImage.value = false
  if (plan) {
    populateFormFromPlan(plan)
    activeMode.value = 'form'
  }
}

function populateFormFromPlan(plan: typeof currentPlan.value) {
  if (!plan) return
  formData.title = plan.title
  formData.aircraft_type = plan.aircraft_type
  formData.departure_icao = plan.departure_icao
  formData.arrival_icao = plan.arrival_icao
  formData.alternate_icao = plan.alternate_icao ?? ''
  formData.route_string = plan.route_string ?? ''
  formData.cruise_altitude_ft = plan.cruise_altitude_ft ?? undefined
  formData.fuel_required_lbs = plan.fuel_required_lbs ?? undefined
  formData.fuel_reserve_lbs = plan.fuel_reserve_lbs ?? undefined
  formData.total_fuel_lbs = plan.total_fuel_lbs ?? undefined
  formData.total_weight_lbs = plan.total_weight_lbs ?? undefined
  formData.max_weight_lbs = plan.max_weight_lbs ?? undefined
  formData.cg_position = plan.cg_position ?? undefined
}

function loadFlightPlan(plan: (typeof flightPlans.value)[number]) {
  router.push(`/flight-plan/${plan.id}`)
}

function handleNewPlan() {
  const { resetState } = useFlightPlans()
  resetState()
  formData.title = ''
  formData.aircraft_type = 'C172'
  formData.departure_icao = ''
  formData.arrival_icao = ''
  formData.alternate_icao = ''
  formData.route_string = ''
  formData.cruise_altitude_ft = undefined
  formData.fuel_required_lbs = undefined
  formData.fuel_reserve_lbs = undefined
  formData.total_fuel_lbs = undefined
  formData.total_weight_lbs = undefined
  formData.max_weight_lbs = maxWeights.C172
  formData.cg_position = undefined
  clearValidation()
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Fetch existing plans on mount
onMounted(async () => {
  formData.max_weight_lbs = maxWeights.C172
  await listFlightPlans()
})
</script>

<template>
  <NuxtLayout name="default">
    <template #header>
      <AppHeader title="Flight Plan Builder" subtitle="PLAN · VALIDATE · EXECUTE">
        <template #action>
          <HButton
            variant="primary"
            size="sm"
            icon="heroicons:plus"
            @click="handleNewPlan"
          >
            NEW PLAN
          </HButton>
        </template>
      </AppHeader>
    </template>

    <template #sidebar>
      <div class="space-y-4">
        <!-- My Flight Plans -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:document-text" class="w-4 h-4 text-horus-accent-cyan" />
            <h2 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider">
              My Flight Plans
            </h2>
          </div>
          <button
            class="text-horus-text-muted hover:text-horus-text-primary transition-colors"
            @click="isSidebarVisible = !isSidebarVisible"
          >
            <Icon
              :name="isSidebarVisible ? 'heroicons:chevron-up' : 'heroicons:chevron-down'"
              class="w-4 h-4"
            />
          </button>
        </div>

        <div v-if="isLoading" class="flex items-center justify-center py-4">
          <Icon name="svg-spinners:ring-resize" class="w-5 h-5 text-horus-accent-cyan" />
        </div>

        <div v-else-if="isSidebarVisible" class="space-y-2">
          <div v-if="flightPlans.length === 0" class="text-center py-4">
            <p class="text-xs text-horus-text-muted">No flight plans yet</p>
          </div>

          <button
            v-for="plan in flightPlans"
            :key="plan.id"
            :class="[
              'w-full text-left p-3 rounded-lg border transition-all',
              currentPlan?.id === plan.id
                ? 'bg-horus-accent-cyan/10 border-horus-accent-cyan/30'
                : 'bg-horus-bg-card/50 border-horus-border-subtle hover:border-horus-accent-cyan/20',
            ]"
            @click="loadFlightPlan(plan)"
          >
            <div class="flex items-start justify-between gap-2 mb-1">
              <span class="text-sm font-medium text-horus-text-primary truncate">
                {{ plan.title || 'Untitled' }}
              </span>
              <HBadge :variant="statusVariant(plan.status)" size="sm">
                {{ plan.status }}
              </HBadge>
            </div>
            <div class="flex items-center gap-2 text-xxs text-horus-text-muted">
              <span class="font-mono">{{ plan.departure_icao }} → {{ plan.arrival_icao }}</span>
              <span>·</span>
              <span>{{ plan.aircraft_type }}</span>
            </div>
            <p class="text-xxs text-horus-text-muted mt-1">
              {{ formatDate(plan.created_at) }}
            </p>
          </button>
        </div>
      </div>
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-4">
        <!-- Error Banner -->
        <div
          v-if="errorMessage"
          class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
        >
          <Icon name="heroicons:exclamation-triangle" class="w-5 h-5 text-horus-status-danger flex-shrink-0" />
          <span class="text-sm text-horus-status-danger">{{ errorMessage }}</span>
          <button
            class="ml-auto text-horus-status-danger hover:text-horus-text-primary"
            @click="() => { /* errorMessage is readonly from composable */ }"
          >
            <Icon name="heroicons:x-mark" class="w-4 h-4" />
          </button>
        </div>

        <!-- Mode Tabs -->
        <div class="flex items-center justify-between">
          <HButtonGroup
            v-model="activeMode"
            :options="[
              { value: 'form', label: 'Form', icon: 'heroicons:pencil-square' },
              { value: 'text', label: 'Text', icon: 'heroicons:document-text' },
              { value: 'image', label: 'Image', icon: 'heroicons:camera' },
            ]"
            size="sm"
          />

          <div v-if="currentPlan" class="flex items-center gap-2">
            <span class="text-xs text-horus-text-muted">Plan #{{ currentPlan.id }}</span>
            <HBadge :variant="statusVariant(currentPlan.status)" size="sm">
              {{ currentPlan.status }}
            </HBadge>
          </div>
        </div>

        <!-- ======================== FORM MODE ======================== -->
        <div v-show="activeMode === 'form'" class="grid gap-4 lg:grid-cols-12">
          <!-- Left: Form Fields -->
          <div class="lg:col-span-3 space-y-4">
            <HCard variant="default" padding="md">
              <div class="space-y-3">
                <h3 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider flex items-center gap-2">
                  <Icon name="heroicons:clipboard-document" class="w-4 h-4 text-horus-accent-cyan" />
                  Plan Details
                </h3>

                <!-- Title -->
                <div class="space-y-1.5">
                  <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Title</label>
                  <input
                    v-model="formData.title"
                    type="text"
                    placeholder="My Flight Plan"
                    class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm text-horus-text-primary placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                  />
                </div>

                <!-- Aircraft Type -->
                <HDropdown
                  v-model="formData.aircraft_type"
                  :options="aircraftOptions"
                  label="Aircraft Type"
                />

                <!-- Departure ICAO -->
                <div class="space-y-1.5">
                  <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Departure ICAO</label>
                  <input
                    v-model="formData.departure_icao"
                    type="text"
                    placeholder="KJFK"
                    maxlength="4"
                    class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm font-mono text-horus-text-primary uppercase placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                  />
                </div>

                <!-- Arrival ICAO -->
                <div class="space-y-1.5">
                  <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Arrival ICAO</label>
                  <input
                    v-model="formData.arrival_icao"
                    type="text"
                    placeholder="KLAX"
                    maxlength="4"
                    class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm font-mono text-horus-text-primary uppercase placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                  />
                </div>

                <!-- Alternate ICAO -->
                <div class="space-y-1.5">
                  <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Alternate ICAO</label>
                  <input
                    v-model="formData.alternate_icao"
                    type="text"
                    placeholder="KBOS (optional)"
                    maxlength="4"
                    class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm font-mono text-horus-text-primary uppercase placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                  />
                </div>

                <!-- Route String -->
                <div class="space-y-1.5">
                  <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Route</label>
                  <textarea
                    v-model="formData.route_string"
                    rows="3"
                    placeholder="DCT MERIT J60 HFD V229 BOSTN"
                    class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm font-mono text-horus-text-primary placeholder-horus-text-muted resize-none focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                  />
                </div>
              </div>
            </HCard>
          </div>

          <!-- Center: Map -->
          <div class="lg:col-span-5">
            <FlightPlanMap
              :departure-lat="depCoords?.lat ?? null"
              :departure-lon="depCoords?.lon ?? null"
              :arrival-lat="arrCoords?.lat ?? null"
              :arrival-lon="arrCoords?.lon ?? null"
              :departure-icao="formData.departure_icao"
              :arrival-icao="formData.arrival_icao"
              :alternate-icao="formData.alternate_icao"
              :legs="currentPlan?.legs ?? []"
              @map-click="(latlng) => { /* Future: add intermediate waypoint */ }"
            />
          </div>

          <!-- Right: Calculations -->
          <div class="lg:col-span-4 space-y-4">
            <!-- Fuel Calculator -->
            <HCard variant="default" padding="md">
              <div class="space-y-3">
                <h3 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider flex items-center gap-2">
                  <Icon name="heroicons:fire" class="w-4 h-4 text-horus-status-warning" />
                  Fuel Calculator
                </h3>

                <div class="space-y-2">
                  <div class="space-y-1.5">
                    <label class="block text-xxs text-horus-text-muted uppercase tracking-wider">Fuel Required (lbs)</label>
                    <input
                      v-model.number="formData.fuel_required_lbs"
                      type="number"
                      placeholder="0"
                      class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-1.5 text-sm font-mono text-horus-text-primary placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                    />
                  </div>
                  <div class="space-y-1.5">
                    <label class="block text-xxs text-horus-text-muted uppercase tracking-wider">Fuel Reserve (lbs)</label>
                    <input
                      v-model.number="formData.fuel_reserve_lbs"
                      type="number"
                      placeholder="0"
                      class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-1.5 text-sm font-mono text-horus-text-primary placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                    />
                  </div>
                  <div class="flex items-center justify-between p-2 rounded bg-horus-bg-tertiary/50 border border-horus-border-subtle">
                    <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Total Fuel</span>
                    <span class="text-sm font-mono font-semibold text-horus-accent-cyan">
                      {{ formData.total_fuel_lbs ?? '--' }} lbs
                    </span>
                  </div>
                </div>
              </div>
            </HCard>

            <!-- Weight & Balance -->
            <HCard variant="default" padding="md">
              <div class="space-y-3">
                <h3 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider flex items-center gap-2">
                  <Icon name="heroicons:scale" class="w-4 h-4 text-horus-status-info" />
                  Weight & Balance
                </h3>

                <div class="space-y-2">
                  <div class="space-y-1.5">
                    <label class="block text-xxs text-horus-text-muted uppercase tracking-wider">Total Weight (lbs)</label>
                    <input
                      v-model.number="formData.total_weight_lbs"
                      type="number"
                      placeholder="0"
                      class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-1.5 text-sm font-mono text-horus-text-primary placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                    />
                  </div>

                  <div class="flex items-center justify-between p-2 rounded bg-horus-bg-tertiary/50 border border-horus-border-subtle">
                    <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Max Weight</span>
                    <span class="text-sm font-mono text-horus-text-secondary">
                      {{ formData.max_weight_lbs ?? '--' }} lbs
                    </span>
                  </div>

                  <div class="space-y-1.5">
                    <label class="block text-xxs text-horus-text-muted uppercase tracking-wider">CG Position (%)</label>
                    <input
                      v-model.number="formData.cg_position"
                      type="number"
                      step="0.1"
                      placeholder="25.0"
                      class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-1.5 text-sm font-mono text-horus-text-primary placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                    />
                  </div>

                  <div
                    v-if="cgWithinLimits !== null"
                    :class="[
                      'flex items-center gap-2 p-2 rounded border',
                      cgWithinLimits
                        ? 'bg-horus-status-success/10 border-horus-status-success/30'
                        : 'bg-horus-status-danger/10 border-horus-status-danger/30',
                    ]"
                  >
                    <Icon
                      :name="cgWithinLimits ? 'heroicons:check-circle-solid' : 'heroicons:x-circle-solid'"
                      :class="['w-4 h-4', cgWithinLimits ? 'text-horus-status-success' : 'text-horus-status-danger']"
                    />
                    <span :class="['text-xs', cgWithinLimits ? 'text-horus-status-success' : 'text-horus-status-danger']">
                      {{ cgWithinLimits ? 'Within weight limits' : 'Exceeds max weight!' }}
                    </span>
                  </div>
                </div>
              </div>
            </HCard>

            <!-- Weather Panel -->
            <HCard variant="default" padding="md">
              <div class="space-y-3">
                <h3 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider flex items-center gap-2">
                  <Icon name="heroicons:cloud" class="w-4 h-4 text-horus-accent-cyan" />
                  Weather
                </h3>

                <div v-if="formData.departure_icao" class="p-2 rounded bg-horus-bg-tertiary/50 border border-horus-border-subtle">
                  <span class="text-xxs text-horus-text-muted uppercase tracking-wider">{{ formData.departure_icao }} METAR</span>
                  <p class="text-xs font-mono text-horus-text-secondary mt-1">
                    Weather data loads after save
                  </p>
                </div>

                <div v-if="formData.arrival_icao" class="p-2 rounded bg-horus-bg-tertiary/50 border border-horus-border-subtle">
                  <span class="text-xxs text-horus-text-muted uppercase tracking-wider">{{ formData.arrival_icao }} METAR</span>
                  <p class="text-xs font-mono text-horus-text-secondary mt-1">
                    Weather data loads after save
                  </p>
                </div>
              </div>
            </HCard>
          </div>
        </div>

        <!-- ======================== TEXT MODE ======================== -->
        <div v-show="activeMode === 'text'" class="max-w-3xl mx-auto space-y-4">
          <HCard variant="default" padding="lg">
            <div class="space-y-4">
              <h3 class="text-sm font-semibold text-horus-text-primary flex items-center gap-2">
                <Icon name="heroicons:document-text" class="w-5 h-5 text-horus-accent-cyan" />
                Parse Flight Plan from Text
              </h3>
              <p class="text-xs text-horus-text-secondary">
                Paste a flight plan, METAR briefing, or route description. The AI will extract departure, arrival, route, and fuel data automatically.
              </p>

              <textarea
                v-model="textInput"
                rows="12"
                placeholder="Paste your flight plan here...

Example:
Flight Plan: VFR
Aircraft: C172
Departure: KJFK at 1400Z
Arrival: KBOS via V229
Altitude: 5500ft
Fuel: 40 gallons required, 8 gallons reserve"
                class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-4 py-3 text-sm font-mono text-horus-text-primary placeholder-horus-text-muted resize-none focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
              />

              <div class="flex justify-end">
                <HButton
                  variant="primary"
                  size="md"
                  icon="heroicons:sparkles"
                  :loading="isParsingText"
                  :disabled="!textInput.trim()"
                  @click="handleParseText"
                >
                  Parse with AI
                </HButton>
              </div>
            </div>
          </HCard>
        </div>

        <!-- ======================== IMAGE MODE ======================== -->
        <div v-show="activeMode === 'image'" class="max-w-3xl mx-auto space-y-4">
          <HCard variant="default" padding="lg">
            <div class="space-y-4">
              <h3 class="text-sm font-semibold text-horus-text-primary flex items-center gap-2">
                <Icon name="heroicons:camera" class="w-5 h-5 text-horus-accent-cyan" />
                Extract Flight Plan from Image
              </h3>
              <p class="text-xs text-horus-text-secondary">
                Upload a photo of a written flight plan, printed form, or whiteboard. OCR will extract the data.
              </p>

              <!-- Drop Zone -->
              <div
                :class="[
                  'relative border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer',
                  imageFile
                    ? 'border-horus-accent-cyan/50 bg-horus-accent-cyan/5'
                    : 'border-horus-border-default hover:border-horus-accent-cyan/30 hover:bg-horus-bg-tertiary/30',
                ]"
                @click="fileInputRef?.click()"
                @dragover.prevent
                @drop="handleImageDrop"
              >
                <input
                  ref="fileInputRef"
                  type="file"
                  accept="image/*"
                  class="hidden"
                  @change="handleImageSelect"
                />

                <template v-if="!imagePreview">
                  <Icon name="heroicons:cloud-arrow-up" class="w-12 h-12 text-horus-text-muted mx-auto mb-3 opacity-60" />
                  <p class="text-sm text-horus-text-secondary">
                    Drag & drop an image or click to browse
                  </p>
                  <p class="text-xxs text-horus-text-muted mt-1">
                    Supports JPG, PNG, WEBP up to 10MB
                  </p>
                </template>

                <template v-else>
                  <img
                    :src="imagePreview"
                    alt="Flight plan image"
                    class="max-h-64 mx-auto rounded-lg border border-horus-border-subtle"
                  />
                  <p class="text-xs text-horus-text-secondary mt-3">
                    {{ imageFile?.name }}
                  </p>
                </template>
              </div>

              <div class="flex items-center justify-between">
                <HButton
                  v-if="imageFile"
                  variant="ghost"
                  size="sm"
                  @click="imageFile = null; imagePreview = null"
                >
                  Clear Image
                </HButton>
                <div class="flex-1" />
                <HButton
                  variant="primary"
                  size="md"
                  icon="heroicons:sparkles"
                  :loading="isParsingImage"
                  :disabled="!imageFile"
                  @click="handleExtractImage"
                >
                  Extract with OCR
                </HButton>
              </div>
            </div>
          </HCard>
        </div>

        <!-- ======================== BOTTOM BAR ======================== -->
        <div class="flex items-center justify-between gap-4 p-4 rounded-lg bg-horus-bg-card/80 border border-horus-border-subtle">
          <div class="flex items-center gap-3">
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:document-arrow-down"
              :loading="isSaving"
              @click="handleSaveDraft"
            >
              Save Draft
            </HButton>

            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:clipboard-document-check"
              :loading="isValidating"
              @click="handleValidate"
            >
              Validate
            </HButton>

            <HButton
              variant="primary"
              size="sm"
              icon="heroicons:rocket-launch"
              :disabled="!canActivate"
              :loading="isSaving"
              @click="handleActivate"
            >
              Activate for Training
            </HButton>
          </div>

          <div v-if="validationResponse" class="flex items-center gap-2">
            <Icon
              :name="validationResponse.is_valid ? 'heroicons:check-circle-solid' : 'heroicons:x-circle-solid'"
              :class="[
                'w-5 h-5',
                validationResponse.is_valid ? 'text-horus-status-success' : 'text-horus-status-danger',
              ]"
            />
            <span
              :class="[
                'text-sm font-medium',
                validationResponse.is_valid ? 'text-horus-status-success' : 'text-horus-status-danger',
              ]"
            >
              {{ validationResponse.is_valid ? 'Valid' : 'Issues Found' }}
            </span>
          </div>
        </div>

        <!-- Validation Panel -->
        <div v-if="validationResponse || isValidating">
          <ValidationPanel
            :results="validationResults"
            :is-loading="isValidating"
          />
        </div>
      </div>
    </template>

    <template #panel>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">QUICK TIPS</h2>
        </div>

        <div class="space-y-3 text-xs text-horus-text-secondary">
          <div class="p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle">
            <p class="font-semibold text-horus-text-primary mb-1">Form Mode</p>
            <p>Enter flight details manually. The map updates as you type ICAO codes.</p>
          </div>
          <div class="p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle">
            <p class="font-semibold text-horus-text-primary mb-1">Text Mode</p>
            <p>Paste any flight plan text — AI extracts all fields automatically.</p>
          </div>
          <div class="p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle">
            <p class="font-semibold text-horus-text-primary mb-1">Image Mode</p>
            <p>Upload a photo of a handwritten or printed flight plan for OCR extraction.</p>
          </div>
        </div>

        <HDataPanel
          :value="String(flightPlans.length)"
          label="Total Plans"
          variant="compact"
        />
      </div>
    </template>
  </NuxtLayout>
</template>
