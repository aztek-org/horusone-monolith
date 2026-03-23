<script setup lang="ts">
import type { FlightPlanCreateData, ValidationResult } from '~/composables/useFlightPlans'

definePageMeta({
  layout: false,
  middleware: 'auth',
})

const route = useRoute()
const router = useRouter()
const planId = computed(() => Number(route.params.id))

const {
  currentPlan,
  isLoading,
  isSaving,
  isValidating,
  errorMessage,
  validationResponse,
  getFlightPlan,
  updateFlightPlan,
  validateFlightPlan,
  activateFlightPlan,
  deleteFlightPlan,
  clearValidation,
} = useFlightPlans()

// Input mode
type InputMode = 'form' | 'text' | 'image'
const activeMode = ref<InputMode>('form')

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

const aircraftOptions = [
  { value: 'C172', label: 'Cessna 172 Skyhawk' },
  { value: 'C182', label: 'Cessna 182 Skylane' },
  { value: 'PA28', label: 'Piper PA-28 Cherokee' },
  { value: 'B738', label: 'Boeing 737-800' },
  { value: 'A320', label: 'Airbus A320' },
]

const maxWeights: Record<string, number> = {
  C172: 2550,
  C182: 3100,
  PA28: 2440,
  B738: 174200,
  A320: 170000,
}

// Airport coords (mock DB)
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

const cgWithinLimits = computed(() => {
  if (formData.total_weight_lbs === undefined || formData.max_weight_lbs === undefined) return null
  return formData.total_weight_lbs <= formData.max_weight_lbs
})

const depCoords = computed(() => {
  const icao = formData.departure_icao.toUpperCase()
  return airportCoords[icao] ?? null
})

const arrCoords = computed(() => {
  const icao = formData.arrival_icao.toUpperCase()
  return airportCoords[icao] ?? null
})

const validationResults = computed<ValidationResult[]>(() => {
  return validationResponse.value?.results ?? []
})

const canActivate = computed(() => {
  return validationResponse.value?.is_valid === true && currentPlan.value?.status === 'validated'
})

function statusVariant(status: string): 'active' | 'warning' | 'info' | 'idle' | 'success' {
  switch (status) {
    case 'draft': return 'idle'
    case 'validated': return 'info'
    case 'active': return 'active'
    case 'completed': return 'success'
    default: return 'idle'
  }
}

function populateFormFromPlan() {
  const plan = currentPlan.value
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

async function handleSave() {
  clearValidation()
  await updateFlightPlan(planId.value, { ...formData })
}

async function handleValidate() {
  await handleSave()
  if (currentPlan.value) {
    await validateFlightPlan(currentPlan.value.id)
  }
}

async function handleActivate() {
  if (currentPlan.value) {
    await activateFlightPlan(currentPlan.value.id)
  }
}

async function handleDelete() {
  if (!confirm('Delete this flight plan?')) return
  const success = await deleteFlightPlan(planId.value)
  if (success) {
    router.push('/flight-plan')
  }
}

// Load on mount
onMounted(async () => {
  const plan = await getFlightPlan(planId.value)
  if (plan) {
    populateFormFromPlan()
  }
})
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader title="Flight Plan Editor" subtitle="EDIT · VALIDATE · ACTIVATE">
        <template #action>
          <div class="flex items-center gap-2">
            <HButton
              variant="ghost"
              size="sm"
              icon="heroicons:arrow-left"
              @click="router.push('/flight-plan')"
            >
              Back
            </HButton>
            <HButton
              variant="danger"
              size="sm"
              icon="heroicons:trash"
              @click="handleDelete"
            >
              Delete
            </HButton>
          </div>
        </template>
      </AppHeader>
    </template>

    <template #sidebar>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:information-circle" class="w-4 h-4 text-horus-accent-cyan" />
          <h2 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider">
            Plan Info
          </h2>
        </div>

        <div v-if="currentPlan" class="space-y-3">
          <div class="p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Status</span>
              <HBadge :variant="statusVariant(currentPlan.status)" size="sm">
                {{ currentPlan.status }}
              </HBadge>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Plan ID</span>
              <span class="text-xs font-mono text-horus-text-primary">#{{ currentPlan.id }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Legs</span>
              <span class="text-xs font-mono text-horus-text-primary">{{ currentPlan.legs?.length ?? 0 }}</span>
            </div>
          </div>

          <!-- Legs List -->
          <HSection
            v-if="currentPlan.legs?.length"
            title="Route Legs"
            icon="heroicons:arrow-long-right"
            collapsible
            :default-expanded="false"
          >
            <div class="space-y-1">
              <div
                v-for="leg in currentPlan.legs"
                :key="leg.id"
                class="flex items-center gap-2 p-2 rounded bg-horus-bg-tertiary/30 border border-horus-border-subtle text-xs"
              >
                <span class="font-mono text-horus-accent-cyan w-6">{{ leg.sequence }}</span>
                <span class="font-mono text-horus-text-primary">{{ leg.from_waypoint }}</span>
                <Icon name="heroicons:arrow-right" class="w-3 h-3 text-horus-text-muted" />
                <span class="font-mono text-horus-text-primary">{{ leg.to_waypoint }}</span>
                <span v-if="leg.altitude_ft" class="ml-auto text-horus-text-muted">
                  {{ leg.altitude_ft }}ft
                </span>
              </div>
            </div>
          </HSection>
        </div>
      </div>
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-4">
        <!-- Loading -->
        <div v-if="isLoading" class="flex items-center justify-center py-16">
          <div class="text-center space-y-3">
            <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
            <p class="text-sm text-horus-text-muted">Loading flight plan...</p>
          </div>
        </div>

        <!-- Error -->
        <div
          v-else-if="errorMessage && !currentPlan"
          class="flex flex-col items-center justify-center py-16 text-center"
        >
          <Icon name="heroicons:exclamation-triangle" class="w-12 h-12 text-horus-status-danger mb-4 opacity-60" />
          <p class="text-sm text-horus-status-danger mb-3">{{ errorMessage }}</p>
          <HButton variant="secondary" size="sm" @click="router.push('/flight-plan')">
            Back to Flight Plans
          </HButton>
        </div>

        <template v-else>
          <!-- Error Banner (non-fatal) -->
          <div
            v-if="errorMessage"
            class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
          >
            <Icon name="heroicons:exclamation-triangle" class="w-5 h-5 text-horus-status-danger flex-shrink-0" />
            <span class="text-sm text-horus-status-danger">{{ errorMessage }}</span>
          </div>

          <!-- Main Content Grid -->
          <div class="grid gap-4 lg:grid-cols-12">
            <!-- Left: Form -->
            <div class="lg:col-span-3 space-y-4">
              <HCard variant="default" padding="md">
                <div class="space-y-3">
                  <h3 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider flex items-center gap-2">
                    <Icon name="heroicons:clipboard-document" class="w-4 h-4 text-horus-accent-cyan" />
                    Plan Details
                  </h3>

                  <div class="space-y-1.5">
                    <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Title</label>
                    <input
                      v-model="formData.title"
                      type="text"
                      placeholder="My Flight Plan"
                      class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm text-horus-text-primary placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                    />
                  </div>

                  <HDropdown
                    v-model="formData.aircraft_type"
                    :options="aircraftOptions"
                    label="Aircraft Type"
                  />

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

                  <div class="space-y-1.5">
                    <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Alternate ICAO</label>
                    <input
                      v-model="formData.alternate_icao"
                      type="text"
                      placeholder="KBOS"
                      maxlength="4"
                      class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-3 py-2 text-sm font-mono text-horus-text-primary uppercase placeholder-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
                    />
                  </div>

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
              />
            </div>

            <!-- Right: Calculations -->
            <div class="lg:col-span-4 space-y-4">
              <!-- Fuel -->
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
                      <span class="text-sm font-mono text-horus-text-secondary">{{ formData.max_weight_lbs ?? '--' }} lbs</span>
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
            </div>
          </div>

          <!-- Bottom Bar -->
          <div class="flex items-center justify-between gap-4 p-4 rounded-lg bg-horus-bg-card/80 border border-horus-border-subtle">
            <div class="flex items-center gap-3">
              <HButton
                variant="secondary"
                size="sm"
                icon="heroicons:document-arrow-down"
                :loading="isSaving"
                @click="handleSave"
              >
                Save Changes
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
        </template>
      </div>
    </template>

    <template #panel>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">PLAN NOTES</h2>
        </div>

        <div v-if="currentPlan" class="space-y-3">
          <HDataPanel
            :value="currentPlan.aircraft_type"
            label="Aircraft"
            variant="compact"
          />
          <HDataPanel
            :value="`${currentPlan.departure_icao} → ${currentPlan.arrival_icao}`"
            label="Route"
            variant="compact"
          />
          <HDataPanel
            v-if="currentPlan.estimated_time_enroute"
            :value="currentPlan.estimated_time_enroute"
            label="ETE"
            variant="compact"
          />
          <HDataPanel
            :value="String(currentPlan.legs?.length ?? 0)"
            label="Legs"
            variant="compact"
          />
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
