<script setup lang="ts">
defineOptions({
  name: 'TowerDashboardPage',
})

definePageMeta({
  layout: false,
  middleware: 'auth',
})

type SeatRole = 'admin' | 'instructor' | 'student'
type BillingPlan = 'starter' | 'growth' | 'enterprise'
type BillingStatus = 'trial' | 'active' | 'past_due' | 'suspended' | 'canceled'
type BillingCycle = 'monthly' | 'yearly'
type ScenarioType = 'training' | 'evaluation' | 'emergency' | 'checkride'
type BadgeTier = 'bronze' | 'silver' | 'gold' | 'platinum' | 'custom'
type BadgeCriteriaType = 'flight_hours' | 'maneuvers' | 'scenarios' | 'assessments' | 'streak' | 'score'

interface OrganizationOverview {
  id: string
  name: string
  slug: string
  logo_url: string | null
  is_active: boolean
  max_seats: number
  billing_plan: BillingPlan
  billing_status: BillingStatus
  billing_cycle: BillingCycle
  created_at: string
  seat_count: number
  active_sessions: number
  scenario_count: number
}

interface SeatMember {
  id: string
  user_id: string
  organization_id: string
  role: string
  is_active: boolean
  joined_at: string
  user_email: string
  user_display_name: string
}

interface TrainingSession {
  id: number
  scenario_id: number | null
  language: string
  status: string
  started_at: string
  ended_at: string | null
}

interface SessionsByDay {
  date: string
  count: number
}

interface PopularScenario {
  scenario_id: number
  name: string
  session_count: number
}

interface AnalyticsOverview {
  total_sessions: number
  completed_sessions: number
  active_sessions: number
  total_scenarios: number
  total_users: number
  sessions_by_day: SessionsByDay[]
  popular_scenarios: PopularScenario[]
}

interface LeaderboardEntry {
  user_id: string
  display_name: string
  email: string
  completed_sessions: number
  total_voice_logs: number
  total_duration_ms: number
  avg_session_duration_ms: number
}

interface ScenarioCatalogItem {
  id: number
  name: string
  description: string | null
  difficulty: number
  airport_icao: string
  runway: string
  weather_preset: 'VFR' | 'MVFR' | 'IFR' | 'LIFR'
  phase: string
  scenario_type: ScenarioType | null
  flight_plan_template: Record<string, string> | null
  org_id: string | null
  created_by: string | null
  created_at: string
}

interface BadgeDefinition {
  id: string
  org_id: string | null
  name: string
  slug: string
  description: string
  icon: string | null
  criteria: {
    type: BadgeCriteriaType
    threshold: number
  }
  category: string
  tier: BadgeTier
  sort_order: number
  is_active: boolean
  created_at: string
}

interface TrainingModuleItem {
  id: string
  name: string
  description: string | null
  org_id: string | null
  created_by: string | null
  is_published: boolean
  difficulty_level: number
  estimated_duration_minutes: number | null
  sort_order: number
  created_at: string
  updated_at: string
}

const roleOptions: SeatRole[] = ['student', 'instructor', 'admin']
const billingPlanOptions: BillingPlan[] = ['starter', 'growth', 'enterprise']
const billingStatusOptions: BillingStatus[] = ['trial', 'active', 'past_due', 'suspended', 'canceled']
const billingCycleOptions: BillingCycle[] = ['monthly', 'yearly']
const scenarioTypeOptions: ScenarioType[] = ['training', 'evaluation', 'emergency', 'checkride']
const scenarioWeatherOptions = ['VFR', 'MVFR', 'IFR', 'LIFR'] as const
const scenarioPhaseOptions = ['ground', 'departure', 'enroute', 'approach', 'landing']
const badgeCategoryOptions = ['flight', 'communication', 'decision', 'procedure', 'safety', 'custom']
const badgeTierOptions: BadgeTier[] = ['bronze', 'silver', 'gold', 'platinum', 'custom']
const badgeCriteriaTypeOptions: BadgeCriteriaType[] = [
  'flight_hours',
  'maneuvers',
  'scenarios',
  'assessments',
  'streak',
  'score',
]

const { user, logout, hasRole, hasAnyRole, seats: authSeats, activeSeat } = useAuth()
const api = useApi()

const orgId = computed(() => user.value?.organizationId ?? null)
const hasTowerAccess = computed(() => hasAnyRole('org-admin', 'instructor'))
const isOrgAdmin = computed(() => hasRole('org-admin'))
const isInstructorOnly = computed(() => hasRole('instructor') && !isOrgAdmin.value)

const organization = ref<OrganizationOverview | null>(null)
const seats = ref<SeatMember[]>([])
const sessions = ref<TrainingSession[]>([])
const analyticsOverview = ref<AnalyticsOverview | null>(null)
const leaderboard = ref<LeaderboardEntry[]>([])
const analyticsError = ref<string | null>(null)
const scenarioCatalog = ref<ScenarioCatalogItem[]>([])
const badges = ref<BadgeDefinition[]>([])
const trainingModules = ref<TrainingModuleItem[]>([])

const isLoading = ref(true)
const pageError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const actionSuccess = ref<string | null>(null)
const isSavingBilling = ref(false)
const isLoadingScenarios = ref(false)
const isCreatingScenario = ref(false)
const isLoadingBadges = ref(false)
const isCreatingBadge = ref(false)
const isLoadingModules = ref(false)
const isCreatingModule = ref(false)

const inviteEmail = ref('')
const inviteRole = ref<SeatRole>('student')
const isInviting = ref(false)
const updatingSeatId = ref<string | null>(null)
const deactivatingSeatId = ref<string | null>(null)
const roleDrafts = ref<Record<string, SeatRole>>({})
const billingPlanDraft = ref<BillingPlan>('starter')
const billingStatusDraft = ref<BillingStatus>('trial')
const billingCycleDraft = ref<BillingCycle>('monthly')
const scenarioForm = ref({
  name: '',
  description: '',
  difficulty: 2,
  airport_icao: '',
  runway: '',
  weather_preset: 'VFR' as (typeof scenarioWeatherOptions)[number],
  phase: 'ground',
  scenario_type: 'training' as ScenarioType,
  template_departure_icao: '',
  template_arrival_icao: '',
  template_route_string: '',
})
const badgeForm = ref({
  name: '',
  description: '',
  category: 'custom',
  tier: 'bronze' as BadgeTier,
  criteria_type: 'scenarios' as BadgeCriteriaType,
  criteria_threshold: 1,
})
const moduleForm = ref({
  name: '',
  description: '',
  difficulty_level: 2,
  estimated_duration_minutes: 30,
  scenario_ids: [] as number[],
})

const recentSessions = computed(() =>
  [...sessions.value]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 10),
)

const activeSessionCount = computed(() =>
  sessions.value.filter(s => s.status === 'active').length,
)

const completedSessionCount = computed(() =>
  sessions.value.filter(s => s.status === 'completed').length,
)

const analyticsCompletionRate = computed(() => {
  if (!analyticsOverview.value) return 0
  if (analyticsOverview.value.total_sessions <= 0) return 0
  return Math.round(
    (analyticsOverview.value.completed_sessions / analyticsOverview.value.total_sessions) * 100,
  )
})

const popularScenarios = computed(() =>
  analyticsOverview.value?.popular_scenarios.slice(0, 3) ?? [],
)

const organizationScenarios = computed(() => {
  if (!orgId.value) return [] as ScenarioCatalogItem[]
  return scenarioCatalog.value
    .filter(scenario => scenario.org_id === orgId.value)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8)
})

const sharedScenarios = computed(() =>
  scenarioCatalog.value
    .filter(scenario => scenario.org_id === null)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 4),
)

const organizationBadges = computed(() => {
  if (!orgId.value) return [] as BadgeDefinition[]
  return badges.value
    .filter(badge => badge.org_id === orgId.value)
    .sort((a, b) => a.sort_order - b.sort_order)
    .slice(0, 8)
})

const sharedBadges = computed(() =>
  badges.value
    .filter(badge => badge.org_id === null)
    .sort((a, b) => a.sort_order - b.sort_order)
    .slice(0, 6),
)

const organizationTrainingModules = computed(() => {
  if (!orgId.value) return [] as TrainingModuleItem[]
  return trainingModules.value
    .filter(module => module.org_id === orgId.value)
    .sort((a, b) => a.sort_order - b.sort_order)
    .slice(0, 8)
})

const sharedTrainingModules = computed(() =>
  trainingModules.value
    .filter(module => module.org_id === null)
    .sort((a, b) => a.sort_order - b.sort_order)
    .slice(0, 6),
)

const moduleScenarioCandidates = computed(() =>
  scenarioCatalog.value
    .filter(scenario => scenario.org_id === null || scenario.org_id === orgId.value)
    .slice(0, 24),
)

const seatCapacityPercent = computed(() => {
  if (!organization.value) return 0
  if (organization.value.max_seats <= 0) return 0
  return Math.min(
    100,
    Math.round((organization.value.seat_count / organization.value.max_seats) * 100),
  )
})

const roleCounts = computed(() => ({
  admin: seats.value.filter(s => s.role === 'admin' && s.is_active).length,
  instructor: seats.value.filter(s => s.role === 'instructor' && s.is_active).length,
  student: seats.value.filter(s => s.role === 'student' && s.is_active).length,
}))

function normalizeSeatRole(role: string): SeatRole {
  if (role === 'admin' || role === 'instructor' || role === 'student') return role
  return 'student'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(session: TrainingSession): string {
  if (!session.ended_at) return 'In progress'
  const start = new Date(session.started_at).getTime()
  const end = new Date(session.ended_at).getTime()
  const mins = Math.max(0, Math.round((end - start) / 60000))
  return `${mins} min`
}

function roleLabel(role: string): string {
  if (role === 'admin') return 'Admin'
  if (role === 'instructor') return 'Instructor'
  return 'Student'
}

function normalizeBillingPlan(plan: string): BillingPlan {
  if (plan === 'starter' || plan === 'growth' || plan === 'enterprise') return plan
  return 'starter'
}

function normalizeBillingStatus(status: string): BillingStatus {
  if (
    status === 'trial'
    || status === 'active'
    || status === 'past_due'
    || status === 'suspended'
    || status === 'canceled'
  ) {
    return status
  }
  return 'trial'
}

function normalizeBillingCycle(cycle: string): BillingCycle {
  if (cycle === 'monthly' || cycle === 'yearly') return cycle
  return 'monthly'
}

function billingPlanLabel(plan: BillingPlan): string {
  if (plan === 'starter') return 'Starter'
  if (plan === 'growth') return 'Growth'
  return 'Enterprise'
}

function billingStatusLabel(status: BillingStatus): string {
  if (status === 'past_due') return 'Past due'
  return `${status.charAt(0).toUpperCase()}${status.slice(1)}`
}

function billingStatusVariant(status: BillingStatus): 'active' | 'warning' | 'danger' | 'idle' {
  if (status === 'active') return 'active'
  if (status === 'trial') return 'idle'
  if (status === 'past_due') return 'warning'
  return 'danger'
}

function billingCycleLabel(cycle: BillingCycle): string {
  return cycle === 'monthly' ? 'Monthly' : 'Yearly'
}

function sessionStatusVariant(status: string): 'active' | 'idle' | 'warning' {
  if (status === 'active') return 'active'
  if (status === 'completed') return 'idle'
  return 'warning'
}

function formatAvgDuration(durationMs: number): string {
  if (durationMs <= 0) return '0 min'
  const mins = Math.round(durationMs / 60000)
  if (mins <= 0) return '<1 min'
  return `${mins} min`
}

function scenarioTypeLabel(type: ScenarioType | null): string {
  if (type === null) return 'General'
  return `${type.charAt(0).toUpperCase()}${type.slice(1)}`
}

function scenarioTypeVariant(type: ScenarioType | null): 'default' | 'info' | 'warning' | 'danger' {
  if (type === 'evaluation') return 'info'
  if (type === 'emergency') return 'danger'
  if (type === 'checkride') return 'warning'
  return 'default'
}

function difficultyLabel(level: number): string {
  if (level >= 4) return 'Advanced'
  if (level >= 2) return 'Intermediate'
  return 'Basic'
}

function normalizeAirportIcao(value: string): string {
  return value.trim().toUpperCase().slice(0, 4)
}

function badgeTierLabel(tier: BadgeTier): string {
  return `${tier.charAt(0).toUpperCase()}${tier.slice(1)}`
}

function criteriaTypeLabel(criteriaType: BadgeCriteriaType): string {
  if (criteriaType === 'flight_hours') return 'Flight hours'
  return criteriaType.replace('_', ' ')
}

function badgeTierVariant(tier: BadgeTier): 'default' | 'info' | 'warning' | 'active' {
  if (tier === 'gold' || tier === 'platinum') return 'warning'
  if (tier === 'silver') return 'info'
  if (tier === 'bronze') return 'default'
  return 'active'
}

function moduleScopeLabel(moduleOrgId: string | null): string {
  return moduleOrgId === null ? 'Shared' : 'Organization'
}

function clearActionBanners() {
  actionError.value = null
  actionSuccess.value = null
}

function setActionError(err: unknown, fallback: string) {
  const apiErr = err as { detail?: string }
  actionError.value = apiErr.detail ?? fallback
  actionSuccess.value = null
}

async function loadOrganization() {
  if (!orgId.value) return
  organization.value = await api.get<OrganizationOverview>(`/api/v1/admin/organizations/${orgId.value}`)
  syncBillingDrafts()
}

async function loadSeats() {
  if (!orgId.value) return
  seats.value = await api.get<SeatMember[]>(`/api/v1/admin/organizations/${orgId.value}/seats`)
  roleDrafts.value = Object.fromEntries(
    seats.value.map(seat => [seat.id, normalizeSeatRole(seat.role)]),
  )
}

async function loadSessions() {
  sessions.value = await api.get<TrainingSession[]>('/api/v1/sessions?limit=100')
}

async function loadScenarioCatalog() {
  isLoadingScenarios.value = true
  try {
    scenarioCatalog.value = await api.get<ScenarioCatalogItem[]>('/api/v1/scenarios?limit=100')
  }
  finally {
    isLoadingScenarios.value = false
  }
}

async function loadBadges() {
  isLoadingBadges.value = true
  try {
    badges.value = await api.get<BadgeDefinition[]>('/api/v1/gamification/badges')
  }
  finally {
    isLoadingBadges.value = false
  }
}

async function loadTrainingModules() {
  isLoadingModules.value = true
  try {
    trainingModules.value = await api.get<TrainingModuleItem[]>('/api/v1/modules/?limit=100')
  }
  finally {
    isLoadingModules.value = false
  }
}

async function loadAnalytics() {
  if (!orgId.value) return

  analyticsError.value = null
  const leaderboardQuery = new URLSearchParams({
    org_id: orgId.value,
    limit: '5',
  })

  try {
    const [overview, board] = await Promise.all([
      api.get<AnalyticsOverview>(`/api/v1/analytics/overview?org_id=${orgId.value}`),
      api.get<LeaderboardEntry[]>(`/api/v1/analytics/leaderboard?${leaderboardQuery.toString()}`),
    ])
    analyticsOverview.value = overview
    leaderboard.value = board
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    analyticsError.value = apiErr.detail ?? 'Unable to load organization progress analytics'
    analyticsOverview.value = null
    leaderboard.value = []
  }
}

function syncBillingDrafts() {
  if (!organization.value) return
  billingPlanDraft.value = normalizeBillingPlan(organization.value.billing_plan)
  billingStatusDraft.value = normalizeBillingStatus(organization.value.billing_status)
  billingCycleDraft.value = normalizeBillingCycle(organization.value.billing_cycle)
}

function resetScenarioForm() {
  scenarioForm.value = {
    name: '',
    description: '',
    difficulty: 2,
    airport_icao: '',
    runway: '',
    weather_preset: 'VFR',
    phase: 'ground',
    scenario_type: 'training',
    template_departure_icao: '',
    template_arrival_icao: '',
    template_route_string: '',
  }
}

function buildScenarioTemplate(): Record<string, string> {
  const template: Record<string, string> = {}
  const departure = normalizeAirportIcao(scenarioForm.value.template_departure_icao)
  const arrival = normalizeAirportIcao(scenarioForm.value.template_arrival_icao)
  const route = scenarioForm.value.template_route_string.trim()

  if (departure) template.departure_icao = departure
  if (arrival) template.arrival_icao = arrival
  if (route) template.route_string = route
  return template
}

function resetBadgeForm() {
  badgeForm.value = {
    name: '',
    description: '',
    category: 'custom',
    tier: 'bronze',
    criteria_type: 'scenarios',
    criteria_threshold: 1,
  }
}

function resetModuleForm() {
  moduleForm.value = {
    name: '',
    description: '',
    difficulty_level: 2,
    estimated_duration_minutes: 30,
    scenario_ids: [],
  }
}

function toggleModuleScenarioSelection(scenarioId: number) {
  if (moduleForm.value.scenario_ids.includes(scenarioId)) {
    moduleForm.value.scenario_ids = moduleForm.value.scenario_ids.filter(id => id !== scenarioId)
    return
  }
  moduleForm.value.scenario_ids = [...moduleForm.value.scenario_ids, scenarioId]
}

function loadInstructorOverview() {
  const seat = activeSeat.value
    ?? authSeats.value.find(currentSeat => currentSeat.organizationId === orgId.value)

  organization.value = {
    id: orgId.value ?? '',
    name: seat?.organizationName ?? 'Organization',
    slug: orgId.value ?? 'unknown',
    logo_url: null,
    is_active: true,
    max_seats: 0,
    billing_plan: 'starter',
    billing_status: 'trial',
    billing_cycle: 'monthly',
    created_at: new Date().toISOString(),
    seat_count: 0,
    active_sessions: activeSessionCount.value,
    scenario_count: 0,
  }
  seats.value = []
  roleDrafts.value = {}
  syncBillingDrafts()
}

async function loadDashboardData() {
  if (!hasTowerAccess.value) {
    isLoading.value = false
    pageError.value = 'This account does not have Tower access.'
    analyticsOverview.value = null
    leaderboard.value = []
    scenarioCatalog.value = []
    badges.value = []
    trainingModules.value = []
    return
  }
  if (!orgId.value) {
    isLoading.value = false
    pageError.value = 'No organization context found in token.'
    analyticsOverview.value = null
    leaderboard.value = []
    scenarioCatalog.value = []
    badges.value = []
    trainingModules.value = []
    return
  }

  isLoading.value = true
  pageError.value = null

  try {
    if (isOrgAdmin.value) {
      await Promise.all([
        loadOrganization(),
        loadSeats(),
        loadSessions(),
        loadAnalytics(),
        loadScenarioCatalog(),
        loadBadges(),
        loadTrainingModules(),
      ])
    }
    else {
      await Promise.all([
        loadSessions(),
        loadAnalytics(),
        loadScenarioCatalog(),
        loadBadges(),
        loadTrainingModules(),
      ])
      loadInstructorOverview()
    }
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    pageError.value = apiErr.detail ?? 'Failed to load Tower operations data'
  }
  finally {
    isLoading.value = false
  }
}

function canSaveBillingProfile(): boolean {
  if (!organization.value || !isOrgAdmin.value) return false
  return (
    billingPlanDraft.value !== organization.value.billing_plan
    || billingStatusDraft.value !== organization.value.billing_status
    || billingCycleDraft.value !== organization.value.billing_cycle
  )
}

async function saveBillingProfile() {
  if (!organization.value || !orgId.value || !isOrgAdmin.value || isSavingBilling.value) return
  if (!canSaveBillingProfile()) return

  isSavingBilling.value = true
  clearActionBanners()
  try {
    const updated = await api.put<OrganizationOverview>(`/api/v1/admin/organizations/${orgId.value}`, {
      billing_plan: billingPlanDraft.value,
      billing_status: billingStatusDraft.value,
      billing_cycle: billingCycleDraft.value,
    })
    organization.value.billing_plan = updated.billing_plan
    organization.value.billing_status = updated.billing_status
    organization.value.billing_cycle = updated.billing_cycle
    syncBillingDrafts()
    actionSuccess.value = 'Billing profile updated.'
  }
  catch (err) {
    setActionError(err, 'Failed to update billing profile')
  }
  finally {
    isSavingBilling.value = false
  }
}

async function createScenario() {
  if (!orgId.value || isCreatingScenario.value) return
  if (!scenarioForm.value.name.trim() || !scenarioForm.value.airport_icao.trim() || !scenarioForm.value.runway.trim()) {
    actionError.value = 'Scenario name, airport ICAO, and runway are required.'
    actionSuccess.value = null
    return
  }

  isCreatingScenario.value = true
  clearActionBanners()
  try {
    const template = buildScenarioTemplate()
    await api.post<ScenarioCatalogItem>('/api/v1/scenarios/', {
      name: scenarioForm.value.name.trim(),
      description: scenarioForm.value.description.trim() || null,
      difficulty: Number(scenarioForm.value.difficulty),
      airport_icao: normalizeAirportIcao(scenarioForm.value.airport_icao),
      runway: scenarioForm.value.runway.trim().toUpperCase(),
      weather_preset: scenarioForm.value.weather_preset,
      phase: scenarioForm.value.phase,
      scenario_type: scenarioForm.value.scenario_type,
      flight_plan_template: template,
    })
    actionSuccess.value = `Scenario ${scenarioForm.value.name.trim()} created.`
    resetScenarioForm()
    if (isOrgAdmin.value) {
      await Promise.all([loadScenarioCatalog(), loadOrganization()])
    }
    else {
      await loadScenarioCatalog()
    }
  }
  catch (err) {
    setActionError(err, 'Failed to create scenario')
  }
  finally {
    isCreatingScenario.value = false
  }
}

async function createTrainingModule() {
  if (isCreatingModule.value) return
  const name = moduleForm.value.name.trim()
  if (!name) {
    actionError.value = 'Training plan name is required.'
    actionSuccess.value = null
    return
  }

  isCreatingModule.value = true
  clearActionBanners()
  try {
    const created = await api.post<TrainingModuleItem>('/api/v1/modules/', {
      name,
      description: moduleForm.value.description.trim() || null,
      difficulty_level: Number(moduleForm.value.difficulty_level),
      estimated_duration_minutes: moduleForm.value.estimated_duration_minutes > 0
        ? Number(moduleForm.value.estimated_duration_minutes)
        : null,
    })
    for (const [sortOrder, scenarioId] of moduleForm.value.scenario_ids.entries()) {
      await api.post(`/api/v1/modules/${created.id}/scenarios`, {
        scenario_id: scenarioId,
        sort_order: sortOrder,
      })
    }
    actionSuccess.value = `Training plan ${name} created.`
    resetModuleForm()
    await loadTrainingModules()
  }
  catch (err) {
    setActionError(err, 'Failed to create training plan')
  }
  finally {
    isCreatingModule.value = false
  }
}

async function createBadge() {
  if (isCreatingBadge.value) return
  const name = badgeForm.value.name.trim()
  const description = badgeForm.value.description.trim()
  if (!name || !description) {
    actionError.value = 'Badge name and description are required.'
    actionSuccess.value = null
    return
  }
  if (badgeForm.value.criteria_threshold < 1) {
    actionError.value = 'Badge threshold must be at least 1.'
    actionSuccess.value = null
    return
  }

  isCreatingBadge.value = true
  clearActionBanners()
  try {
    await api.post('/api/v1/gamification/badges', {
      name,
      description,
      category: badgeForm.value.category,
      tier: badgeForm.value.tier,
      criteria: {
        type: badgeForm.value.criteria_type,
        threshold: badgeForm.value.criteria_threshold,
      },
    })
    actionSuccess.value = `Badge ${name} created.`
    resetBadgeForm()
    await loadBadges()
  }
  catch (err) {
    setActionError(err, 'Failed to create badge')
  }
  finally {
    isCreatingBadge.value = false
  }
}

async function inviteSeat() {
  if (!orgId.value || !isOrgAdmin.value || isInviting.value) return
  if (!inviteEmail.value.trim()) {
    actionError.value = 'Email is required to invite a seat.'
    actionSuccess.value = null
    return
  }

  isInviting.value = true
  clearActionBanners()
  try {
    await api.post<SeatMember>(`/api/v1/admin/organizations/${orgId.value}/seats`, {
      email: inviteEmail.value.trim().toLowerCase(),
      role: inviteRole.value,
    })
    actionSuccess.value = `Seat invited for ${inviteEmail.value.trim().toLowerCase()}.`
    inviteEmail.value = ''
    inviteRole.value = 'student'
    await Promise.all([loadOrganization(), loadSeats()])
  }
  catch (err) {
    setActionError(err, 'Failed to invite seat')
  }
  finally {
    isInviting.value = false
  }
}

function canSaveSeatRole(seat: SeatMember): boolean {
  const draftRole = roleDrafts.value[seat.id]
  return !!draftRole && draftRole !== normalizeSeatRole(seat.role)
}

async function saveSeatRole(seat: SeatMember) {
  if (!orgId.value || !isOrgAdmin.value || updatingSeatId.value) return
  const draftRole = roleDrafts.value[seat.id]
  if (!draftRole || draftRole === normalizeSeatRole(seat.role)) return

  updatingSeatId.value = seat.id
  clearActionBanners()

  try {
    const updatedSeat = await api.put<SeatMember>(
      `/api/v1/admin/organizations/${orgId.value}/seats/${seat.id}`,
      { role: draftRole },
    )
    seat.role = updatedSeat.role
    roleDrafts.value[seat.id] = normalizeSeatRole(updatedSeat.role)
    actionSuccess.value = `${seat.user_display_name} role updated to ${roleLabel(updatedSeat.role)}.`
  }
  catch (err) {
    setActionError(err, `Failed to update role for ${seat.user_display_name}`)
  }
  finally {
    updatingSeatId.value = null
  }
}

async function deactivateSeat(seat: SeatMember) {
  if (!orgId.value || !isOrgAdmin.value || !seat.is_active || deactivatingSeatId.value) return
  if (!window.confirm(`Deactivate seat for ${seat.user_display_name} (${seat.user_email})?`)) return

  deactivatingSeatId.value = seat.id
  clearActionBanners()

  try {
    await api.del(`/api/v1/admin/organizations/${orgId.value}/seats/${seat.id}`)
    actionSuccess.value = `${seat.user_display_name} seat was deactivated.`
    await Promise.all([loadOrganization(), loadSeats()])
  }
  catch (err) {
    setActionError(err, `Failed to deactivate seat for ${seat.user_display_name}`)
  }
  finally {
    deactivatingSeatId.value = null
  }
}

onMounted(() => {
  loadDashboardData()
})

watch(orgId, (currentOrgId, previousOrgId) => {
  if (currentOrgId && currentOrgId !== previousOrgId) {
    loadDashboardData()
  }
})
</script>

<template>
  <div class="min-h-screen bg-horus-bg-primary px-4 py-6 lg:px-8">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <header class="rounded-xl border border-white/10 bg-horus-bg-secondary p-5 lg:p-6">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 class="text-2xl font-semibold text-horus-text-primary">Tower Operations Dashboard</h1>
            <p class="mt-1 text-sm text-horus-text-secondary">
              Organization admin and instructor operational workspace.
            </p>
            <p class="mt-2 text-xs text-horus-text-muted">
              Signed in as
              <span class="font-medium text-horus-text-primary">
                {{ user?.displayName || user?.email }}
              </span>
            </p>
          </div>
          <div class="flex items-center gap-2">
            <NuxtLink to="/settings">
              <HButton variant="secondary" size="sm" icon="heroicons:cog-6-tooth">
                Settings
              </HButton>
            </NuxtLink>
            <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadDashboardData">
              Refresh
            </HButton>
            <HButton variant="ghost" size="sm" icon="heroicons:arrow-right-on-rectangle" @click="logout()">
              Sign out
            </HButton>
          </div>
        </div>
      </header>

      <div
        v-if="!hasTowerAccess"
        class="rounded-xl border border-horus-status-warning/40 bg-horus-status-warning/10 p-4"
      >
        <p class="text-sm text-horus-status-warning">
          This account cannot access Tower operations. Org-admin or instructor role is required.
        </p>
      </div>

      <div
        v-else-if="pageError"
        class="rounded-xl border border-horus-status-danger/40 bg-horus-status-danger/10 p-4"
      >
        <p class="text-sm text-horus-status-danger">{{ pageError }}</p>
      </div>

      <div v-else-if="isLoading" class="flex items-center justify-center py-20">
        <Icon name="svg-spinners:ring-resize" class="h-8 w-8 text-horus-accent-cyan" />
      </div>

      <template v-else>
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Organization</p>
            <p class="mt-2 text-lg font-semibold text-horus-text-primary">{{ organization?.name }}</p>
            <p class="text-xs text-horus-text-muted">{{ organization?.slug }}</p>
          </HCard>

          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Seat Capacity</p>
            <p class="mt-2 text-lg font-semibold text-horus-text-primary">
              <template v-if="(organization?.max_seats ?? 0) > 0">
                {{ organization?.seat_count ?? 0 }} / {{ organization?.max_seats ?? 0 }}
              </template>
              <template v-else>N/A</template>
            </p>
            <div class="mt-3">
              <HProgress :value="seatCapacityPercent" :show-percentage="false" size="sm" />
            </div>
          </HCard>

          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Active Sessions</p>
            <p class="mt-2 text-lg font-semibold text-horus-text-primary">{{ activeSessionCount }}</p>
            <p class="text-xs text-horus-text-muted">{{ completedSessionCount }} completed</p>
          </HCard>

          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Scenarios</p>
            <p class="mt-2 text-lg font-semibold text-horus-text-primary">
              {{ organization?.scenario_count ?? 0 }}
            </p>
            <p class="text-xs text-horus-text-muted">
              Org active: {{ organization?.is_active ? 'Yes' : 'No' }}
            </p>
          </HCard>
        </div>

        <div
          v-if="actionError"
          class="rounded-lg border border-horus-status-danger/40 bg-horus-status-danger/10 p-3"
        >
          <p class="text-sm text-horus-status-danger">{{ actionError }}</p>
        </div>

        <div
          v-if="actionSuccess"
          class="rounded-lg border border-horus-status-success/40 bg-horus-status-success/10 p-3"
        >
          <p class="text-sm text-horus-status-success">{{ actionSuccess }}</p>
        </div>

        <HCard variant="default" padding="md">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 class="text-sm font-semibold text-horus-text-primary">Organization Billing Profile</h2>
              <p class="text-xs text-horus-text-muted">
                Billing plan and payment status for this organization.
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <HBadge variant="info" size="sm">
                {{ organization ? billingPlanLabel(organization.billing_plan) : 'Starter' }}
              </HBadge>
              <HBadge
                size="sm"
                :variant="organization ? billingStatusVariant(organization.billing_status) : 'idle'"
              >
                {{ organization ? billingStatusLabel(organization.billing_status) : 'Trial' }}
              </HBadge>
              <HBadge variant="default" size="sm">
                {{ organization ? billingCycleLabel(organization.billing_cycle) : 'Monthly' }}
              </HBadge>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-3">
            <select
              v-model="billingPlanDraft"
              :disabled="!isOrgAdmin"
              class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none disabled:opacity-60"
            >
              <option v-for="plan in billingPlanOptions" :key="plan" :value="plan">
                {{ billingPlanLabel(plan) }}
              </option>
            </select>
            <select
              v-model="billingStatusDraft"
              :disabled="!isOrgAdmin"
              class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none disabled:opacity-60"
            >
              <option v-for="status in billingStatusOptions" :key="status" :value="status">
                {{ billingStatusLabel(status) }}
              </option>
            </select>
            <select
              v-model="billingCycleDraft"
              :disabled="!isOrgAdmin"
              class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none disabled:opacity-60"
            >
              <option v-for="cycle in billingCycleOptions" :key="cycle" :value="cycle">
                {{ billingCycleLabel(cycle) }}
              </option>
            </select>
          </div>

          <div class="mt-3 flex items-center justify-between gap-3">
            <p class="text-xs text-horus-text-muted">
              {{ isOrgAdmin ? 'Org-admin can update billing profile fields.' : 'Instructor view is read-only.' }}
            </p>
            <HButton
              variant="secondary"
              size="sm"
              :disabled="!canSaveBillingProfile()"
              :loading="isSavingBilling"
              @click="saveBillingProfile"
            >
              Save Billing
            </HButton>
          </div>
        </HCard>

        <HCard variant="default" padding="md">
          <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-sm font-semibold text-horus-text-primary">Badge Studio</h2>
              <p class="text-xs text-horus-text-muted">
                Create organization-specific achievement badges for trainees.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <HBadge variant="info" size="sm">Org {{ organizationBadges.length }}</HBadge>
              <HBadge variant="default" size="sm">Shared {{ sharedBadges.length }}</HBadge>
            </div>
          </div>

          <div class="grid gap-6 lg:grid-cols-2">
            <div class="space-y-3 rounded-lg border border-white/10 bg-horus-bg-tertiary/30 p-4">
              <p class="text-xxs font-semibold uppercase tracking-wider text-horus-text-secondary">
                Create Badge
              </p>
              <input
                v-model="badgeForm.name"
                type="text"
                placeholder="Badge name"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              >
              <textarea
                v-model="badgeForm.description"
                rows="3"
                placeholder="Badge description"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              />
              <div class="grid gap-2 sm:grid-cols-2">
                <select
                  v-model="badgeForm.category"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="category in badgeCategoryOptions" :key="category" :value="category">
                    {{ category.charAt(0).toUpperCase() + category.slice(1) }}
                  </option>
                </select>
                <select
                  v-model="badgeForm.tier"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="tier in badgeTierOptions" :key="tier" :value="tier">
                    {{ badgeTierLabel(tier) }}
                  </option>
                </select>
                <select
                  v-model="badgeForm.criteria_type"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option
                    v-for="criteriaType in badgeCriteriaTypeOptions"
                    :key="criteriaType"
                    :value="criteriaType"
                  >
                    {{ criteriaTypeLabel(criteriaType) }}
                  </option>
                </select>
                <input
                  v-model.number="badgeForm.criteria_threshold"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="Threshold"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
              </div>
              <div class="flex justify-end">
                <HButton
                  variant="primary"
                  size="sm"
                  icon="heroicons:trophy"
                  :loading="isCreatingBadge"
                  @click="createBadge"
                >
                  Create Badge
                </HButton>
              </div>
            </div>

            <div class="space-y-4">
              <div v-if="isLoadingBadges" class="flex items-center justify-center py-10">
                <Icon name="svg-spinners:ring-resize" class="h-6 w-6 text-horus-accent-cyan" />
              </div>

              <template v-else>
                <div class="space-y-2">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">
                    Organization Badges
                  </p>
                  <div v-if="organizationBadges.length === 0" class="rounded-lg border border-white/10 p-3">
                    <p class="text-xs text-horus-text-muted">No organization badges yet.</p>
                  </div>
                  <template v-else>
                    <div
                      v-for="badge in organizationBadges"
                      :key="`org-badge-${badge.id}`"
                      class="rounded-lg border border-white/10 p-3"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div>
                          <p class="text-sm font-medium text-horus-text-primary">{{ badge.name }}</p>
                          <p class="text-xs text-horus-text-muted">{{ badge.description }}</p>
                          <p class="mt-1 text-xxs text-horus-text-muted">
                            {{ criteriaTypeLabel(badge.criteria.type) }} · threshold {{ badge.criteria.threshold }}
                          </p>
                        </div>
                        <div class="flex flex-wrap justify-end gap-1">
                          <HBadge :variant="badgeTierVariant(badge.tier)" size="sm">
                            {{ badgeTierLabel(badge.tier) }}
                          </HBadge>
                          <HBadge variant="default" size="sm">{{ badge.category }}</HBadge>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>

                <div class="space-y-2">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Shared Badges</p>
                  <div v-if="sharedBadges.length === 0" class="rounded-lg border border-white/10 p-3">
                    <p class="text-xs text-horus-text-muted">No shared badges available.</p>
                  </div>
                  <template v-else>
                    <div
                      v-for="badge in sharedBadges"
                      :key="`shared-badge-${badge.id}`"
                      class="rounded-lg border border-white/10 p-3"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div>
                          <p class="text-sm font-medium text-horus-text-primary">{{ badge.name }}</p>
                          <p class="text-xs text-horus-text-muted">{{ badge.description }}</p>
                        </div>
                        <HBadge :variant="badgeTierVariant(badge.tier)" size="sm">
                          {{ badgeTierLabel(badge.tier) }}
                        </HBadge>
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </div>
          </div>
        </HCard>

        <HCard variant="default" padding="md">
          <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-sm font-semibold text-horus-text-primary">Training Plan Studio</h2>
              <p class="text-xs text-horus-text-muted">
                Build organization training plans by grouping scenarios into modules.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <HBadge variant="info" size="sm">Org {{ organizationTrainingModules.length }}</HBadge>
              <HBadge variant="default" size="sm">Shared {{ sharedTrainingModules.length }}</HBadge>
            </div>
          </div>

          <div class="grid gap-6 lg:grid-cols-2">
            <div class="space-y-3 rounded-lg border border-white/10 bg-horus-bg-tertiary/30 p-4">
              <p class="text-xxs font-semibold uppercase tracking-wider text-horus-text-secondary">
                Create Training Plan
              </p>
              <input
                v-model="moduleForm.name"
                type="text"
                placeholder="Plan name"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              >
              <textarea
                v-model="moduleForm.description"
                rows="3"
                placeholder="Plan description"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              />
              <div class="grid gap-2 sm:grid-cols-2">
                <select
                  v-model.number="moduleForm.difficulty_level"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option :value="1">1 - Basic</option>
                  <option :value="2">2 - Intermediate</option>
                  <option :value="3">3 - Intermediate+</option>
                  <option :value="4">4 - Advanced</option>
                  <option :value="5">5 - Expert</option>
                </select>
                <input
                  v-model.number="moduleForm.estimated_duration_minutes"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="Estimated minutes"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
              </div>
              <div class="space-y-2">
                <p class="text-xxs uppercase tracking-wider text-horus-text-muted">
                  Attach Scenarios ({{ moduleForm.scenario_ids.length }} selected)
                </p>
                <div v-if="moduleScenarioCandidates.length === 0" class="rounded-lg border border-white/10 p-3">
                  <p class="text-xs text-horus-text-muted">No scenarios available yet.</p>
                </div>
                <div
                  v-else
                  class="max-h-40 space-y-2 overflow-y-auto rounded-lg border border-white/10 bg-horus-bg-primary/60 p-3"
                >
                  <label
                    v-for="scenario in moduleScenarioCandidates"
                    :key="`module-scenario-${scenario.id}`"
                    class="flex cursor-pointer items-center justify-between gap-2 text-xs text-horus-text-secondary"
                  >
                    <span class="truncate">{{ scenario.name }}</span>
                    <input
                      :checked="moduleForm.scenario_ids.includes(scenario.id)"
                      type="checkbox"
                      class="h-4 w-4 rounded border-white/20 bg-horus-bg-primary"
                      @change="toggleModuleScenarioSelection(scenario.id)"
                    >
                  </label>
                </div>
              </div>
              <div class="flex justify-end">
                <HButton
                  variant="primary"
                  size="sm"
                  icon="heroicons:clipboard-document-list"
                  :loading="isCreatingModule"
                  @click="createTrainingModule"
                >
                  Create Plan
                </HButton>
              </div>
            </div>

            <div class="space-y-4">
              <div v-if="isLoadingModules" class="flex items-center justify-center py-10">
                <Icon name="svg-spinners:ring-resize" class="h-6 w-6 text-horus-accent-cyan" />
              </div>

              <template v-else>
                <div class="space-y-2">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">
                    Organization Plans
                  </p>
                  <div
                    v-if="organizationTrainingModules.length === 0"
                    class="rounded-lg border border-white/10 p-3"
                  >
                    <p class="text-xs text-horus-text-muted">No organization plans yet.</p>
                  </div>
                  <template v-else>
                    <div
                      v-for="module in organizationTrainingModules"
                      :key="`org-module-${module.id}`"
                      class="rounded-lg border border-white/10 p-3"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div>
                          <p class="text-sm font-medium text-horus-text-primary">{{ module.name }}</p>
                          <p v-if="module.description" class="text-xs text-horus-text-muted">
                            {{ module.description }}
                          </p>
                          <p class="mt-1 text-xxs text-horus-text-muted">
                            {{ module.estimated_duration_minutes ?? 'N/A' }} min ·
                            {{ formatDate(module.updated_at) }}
                          </p>
                        </div>
                        <div class="flex flex-wrap justify-end gap-1">
                          <HBadge variant="default" size="sm">
                            {{ difficultyLabel(module.difficulty_level) }}
                          </HBadge>
                          <HBadge :variant="module.is_published ? 'active' : 'idle'" size="sm">
                            {{ module.is_published ? 'Published' : 'Draft' }}
                          </HBadge>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>

                <div class="space-y-2">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Shared Plans</p>
                  <div v-if="sharedTrainingModules.length === 0" class="rounded-lg border border-white/10 p-3">
                    <p class="text-xs text-horus-text-muted">No shared plans available.</p>
                  </div>
                  <template v-else>
                    <div
                      v-for="module in sharedTrainingModules"
                      :key="`shared-module-${module.id}`"
                      class="rounded-lg border border-white/10 p-3"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div>
                          <p class="text-sm font-medium text-horus-text-primary">{{ module.name }}</p>
                          <p v-if="module.description" class="text-xs text-horus-text-muted">
                            {{ module.description }}
                          </p>
                        </div>
                        <HBadge variant="info" size="sm">{{ moduleScopeLabel(module.org_id) }}</HBadge>
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </div>
          </div>
        </HCard>

        <div class="grid gap-6 lg:grid-cols-2">
          <HCard variant="default" padding="md">
            <div class="mb-4">
              <h2 class="text-sm font-semibold text-horus-text-primary">Training Progress Snapshot</h2>
              <p class="text-xs text-horus-text-muted">
                Organization-level completion trend and scenario demand.
              </p>
            </div>

            <div
              v-if="analyticsError"
              class="rounded-lg border border-horus-status-warning/40 bg-horus-status-warning/10 p-3"
            >
              <p class="text-xs text-horus-status-warning">{{ analyticsError }}</p>
            </div>

            <div v-else-if="analyticsOverview" class="space-y-4">
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="rounded-lg border border-white/10 bg-horus-bg-tertiary/40 p-3">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Total Sessions</p>
                  <p class="mt-1 text-lg font-semibold text-horus-text-primary">
                    {{ analyticsOverview.total_sessions }}
                  </p>
                </div>
                <div class="rounded-lg border border-white/10 bg-horus-bg-tertiary/40 p-3">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Completed</p>
                  <p class="mt-1 text-lg font-semibold text-horus-text-primary">
                    {{ analyticsOverview.completed_sessions }}
                  </p>
                </div>
                <div class="rounded-lg border border-white/10 bg-horus-bg-tertiary/40 p-3">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Active</p>
                  <p class="mt-1 text-lg font-semibold text-horus-text-primary">
                    {{ analyticsOverview.active_sessions }}
                  </p>
                </div>
                <div class="rounded-lg border border-white/10 bg-horus-bg-tertiary/40 p-3">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Active Seats</p>
                  <p class="mt-1 text-lg font-semibold text-horus-text-primary">
                    {{ analyticsOverview.total_users }}
                  </p>
                </div>
              </div>

              <div>
                <div class="mb-2 flex items-center justify-between text-xs text-horus-text-muted">
                  <span>Completion Rate</span>
                  <span class="font-medium text-horus-text-primary">{{ analyticsCompletionRate }}%</span>
                </div>
                <HProgress :value="analyticsCompletionRate" :show-percentage="false" size="sm" />
              </div>

              <div class="space-y-2">
                <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Most Used Scenarios</p>
                <div v-if="popularScenarios.length === 0" class="rounded-lg border border-white/10 p-3">
                  <p class="text-xs text-horus-text-muted">No scenario activity yet.</p>
                </div>
                <div v-else class="space-y-2">
                  <div
                    v-for="scenario in popularScenarios"
                    :key="scenario.scenario_id"
                    class="flex items-center justify-between rounded-lg border border-white/10 p-3"
                  >
                    <p class="text-sm text-horus-text-primary">{{ scenario.name }}</p>
                    <HBadge variant="default" size="sm">
                      {{ scenario.session_count }} sessions
                    </HBadge>
                  </div>
                </div>
              </div>
            </div>
          </HCard>

          <HCard variant="default" padding="md">
            <div class="mb-4">
              <h2 class="text-sm font-semibold text-horus-text-primary">Top Trainees</h2>
              <p class="text-xs text-horus-text-muted">
                Leaderboard by completed sessions inside your organization.
              </p>
            </div>

            <div v-if="leaderboard.length === 0" class="rounded-lg border border-white/10 p-4 text-center">
              <p class="text-sm text-horus-text-muted">
                {{ analyticsError ? 'Leaderboard unavailable.' : 'No completed-session leaderboard yet.' }}
              </p>
            </div>

            <div v-else class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-horus-border-subtle text-left text-xxs uppercase tracking-wider text-horus-text-muted">
                    <th class="pb-2 pr-3">Trainee</th>
                    <th class="pb-2 pr-3">Completed</th>
                    <th class="pb-2 pr-3">Avg Duration</th>
                    <th class="pb-2">Voice Logs</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="entry in leaderboard"
                    :key="entry.user_id"
                    class="border-b border-horus-border-subtle/40"
                  >
                    <td class="py-3 pr-3">
                      <p class="font-medium text-horus-text-primary">{{ entry.display_name }}</p>
                      <p class="text-xs text-horus-text-muted">{{ entry.email }}</p>
                    </td>
                    <td class="py-3 pr-3 text-horus-text-secondary">{{ entry.completed_sessions }}</td>
                    <td class="py-3 pr-3 text-xs text-horus-text-muted">
                      {{ formatAvgDuration(entry.avg_session_duration_ms) }}
                    </td>
                    <td class="py-3 text-horus-text-secondary">{{ entry.total_voice_logs }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </HCard>
        </div>

        <HCard variant="default" padding="md">
          <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-sm font-semibold text-horus-text-primary">Scenario & Plan Studio</h2>
              <p class="text-xs text-horus-text-muted">
                Create organization scenarios with optional flight-plan template metadata.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <HBadge variant="info" size="sm">Org {{ organizationScenarios.length }}</HBadge>
              <HBadge variant="default" size="sm">Shared {{ sharedScenarios.length }}</HBadge>
            </div>
          </div>

          <div class="grid gap-6 lg:grid-cols-2">
            <div class="space-y-3 rounded-lg border border-white/10 bg-horus-bg-tertiary/30 p-4">
              <p class="text-xxs font-semibold uppercase tracking-wider text-horus-text-secondary">
                Create Scenario
              </p>
              <div class="grid gap-2 sm:grid-cols-2">
                <input
                  v-model="scenarioForm.name"
                  type="text"
                  placeholder="Scenario name"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <input
                  v-model="scenarioForm.airport_icao"
                  type="text"
                  maxlength="4"
                  placeholder="Airport ICAO"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm uppercase text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <input
                  v-model="scenarioForm.runway"
                  type="text"
                  placeholder="Runway"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm uppercase text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <select
                  v-model="scenarioForm.weather_preset"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="weather in scenarioWeatherOptions" :key="weather" :value="weather">
                    {{ weather }}
                  </option>
                </select>
                <select
                  v-model.number="scenarioForm.difficulty"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option :value="1">1 - Basic</option>
                  <option :value="2">2 - Intermediate</option>
                  <option :value="3">3 - Intermediate+</option>
                  <option :value="4">4 - Advanced</option>
                  <option :value="5">5 - Expert</option>
                </select>
                <select
                  v-model="scenarioForm.phase"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="phase in scenarioPhaseOptions" :key="phase" :value="phase">
                    {{ phase }}
                  </option>
                </select>
                <select
                  v-model="scenarioForm.scenario_type"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="type in scenarioTypeOptions" :key="type" :value="type">
                    {{ scenarioTypeLabel(type) }}
                  </option>
                </select>
                <input
                  v-model="scenarioForm.template_departure_icao"
                  type="text"
                  maxlength="4"
                  placeholder="Template dep ICAO (optional)"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm uppercase text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <input
                  v-model="scenarioForm.template_arrival_icao"
                  type="text"
                  maxlength="4"
                  placeholder="Template arr ICAO (optional)"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm uppercase text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
              </div>
              <textarea
                v-model="scenarioForm.template_route_string"
                rows="2"
                placeholder="Optional template route string"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              />
              <textarea
                v-model="scenarioForm.description"
                rows="3"
                placeholder="Scenario description (optional)"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              />
              <div class="flex justify-end">
                <HButton
                  variant="primary"
                  size="sm"
                  icon="heroicons:plus"
                  :loading="isCreatingScenario"
                  @click="createScenario"
                >
                  Create Scenario
                </HButton>
              </div>
            </div>

            <div class="space-y-4">
              <div v-if="isLoadingScenarios" class="flex items-center justify-center py-10">
                <Icon name="svg-spinners:ring-resize" class="h-6 w-6 text-horus-accent-cyan" />
              </div>

              <template v-else>
                <div class="space-y-2">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">
                    Organization Scenarios
                  </p>
                  <div v-if="organizationScenarios.length === 0" class="rounded-lg border border-white/10 p-3">
                    <p class="text-xs text-horus-text-muted">No organization scenarios yet.</p>
                  </div>
                  <template v-else>
                    <div
                      v-for="scenario in organizationScenarios"
                      :key="`org-${scenario.id}`"
                      class="rounded-lg border border-white/10 p-3"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div>
                          <p class="text-sm font-medium text-horus-text-primary">{{ scenario.name }}</p>
                          <p class="text-xs text-horus-text-muted">
                            {{ scenario.airport_icao }} · RWY {{ scenario.runway }} · {{ scenario.phase }}
                          </p>
                        </div>
                        <div class="flex flex-wrap justify-end gap-1">
                          <HBadge :variant="scenarioTypeVariant(scenario.scenario_type)" size="sm">
                            {{ scenarioTypeLabel(scenario.scenario_type) }}
                          </HBadge>
                          <HBadge variant="default" size="sm">{{ difficultyLabel(scenario.difficulty) }}</HBadge>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>

                <div class="space-y-2">
                  <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Shared Scenarios</p>
                  <div v-if="sharedScenarios.length === 0" class="rounded-lg border border-white/10 p-3">
                    <p class="text-xs text-horus-text-muted">No shared scenarios available.</p>
                  </div>
                  <template v-else>
                    <div
                      v-for="scenario in sharedScenarios"
                      :key="`shared-${scenario.id}`"
                      class="rounded-lg border border-white/10 p-3"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div>
                          <p class="text-sm font-medium text-horus-text-primary">{{ scenario.name }}</p>
                          <p class="text-xs text-horus-text-muted">
                            {{ scenario.airport_icao }} · RWY {{ scenario.runway }}
                          </p>
                        </div>
                        <HBadge :variant="scenarioTypeVariant(scenario.scenario_type)" size="sm">
                          {{ scenarioTypeLabel(scenario.scenario_type) }}
                        </HBadge>
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </div>
          </div>
        </HCard>

        <div class="grid gap-6 lg:grid-cols-2">
          <HCard variant="default" padding="md">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-horus-text-primary">Members & Seats</h2>
                <p class="text-xs text-horus-text-muted">
                  Organization membership and seat access control.
                </p>
              </div>
              <div class="flex items-center gap-2">
                <HBadge variant="info" size="sm">Admin {{ roleCounts.admin }}</HBadge>
                <HBadge variant="cyan" size="sm">Instructor {{ roleCounts.instructor }}</HBadge>
                <HBadge variant="default" size="sm">Student {{ roleCounts.student }}</HBadge>
              </div>
            </div>

            <div
              v-if="isInstructorOnly"
              class="mb-4 rounded-lg border border-horus-status-warning/40 bg-horus-status-warning/10 p-3"
            >
              <p class="text-xs text-horus-status-warning">
                Seat management requires the org-admin role. Instructor view is read-only.
              </p>
            </div>

            <div v-if="isOrgAdmin" class="mb-4 rounded-lg border border-white/10 bg-horus-bg-tertiary/40 p-3">
              <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-horus-text-secondary">
                Invite Seat
              </p>
              <div class="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
                <input
                  v-model="inviteEmail"
                  type="email"
                  placeholder="pilot@example.com"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <select
                  v-model="inviteRole"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="role in roleOptions" :key="role" :value="role">{{ roleLabel(role) }}</option>
                </select>
                <HButton
                  variant="primary"
                  size="sm"
                  icon="heroicons:user-plus"
                  :loading="isInviting"
                  @click="inviteSeat"
                >
                  Invite
                </HButton>
              </div>
            </div>

            <div v-if="seats.length === 0" class="rounded-lg border border-white/10 p-4 text-center">
              <p class="text-sm text-horus-text-muted">
                {{ isOrgAdmin ? 'No seats found for this organization.' : 'Seat list is org-admin only.' }}
              </p>
            </div>

            <div v-else class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-horus-border-subtle text-left text-xxs uppercase tracking-wider text-horus-text-muted">
                    <th class="pb-2 pr-3">Member</th>
                    <th class="pb-2 pr-3">Role</th>
                    <th class="pb-2 pr-3">Status</th>
                    <th class="pb-2 pr-3">Joined</th>
                    <th class="pb-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="seat in seats"
                    :key="seat.id"
                    class="border-b border-horus-border-subtle/40 align-top"
                  >
                    <td class="py-3 pr-3">
                      <p class="font-medium text-horus-text-primary">{{ seat.user_display_name }}</p>
                      <p class="text-xs text-horus-text-muted">{{ seat.user_email }}</p>
                    </td>
                    <td class="py-3 pr-3">
                      <template v-if="isOrgAdmin">
                        <div class="flex items-center gap-2">
                          <select
                            v-model="roleDrafts[seat.id]"
                            class="rounded-md border border-white/15 bg-horus-bg-primary px-2 py-1 text-xs text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                          >
                            <option v-for="role in roleOptions" :key="role" :value="role">
                              {{ roleLabel(role) }}
                            </option>
                          </select>
                          <HButton
                            variant="secondary"
                            size="sm"
                            :disabled="!canSaveSeatRole(seat)"
                            :loading="updatingSeatId === seat.id"
                            @click="saveSeatRole(seat)"
                          >
                            Save
                          </HButton>
                        </div>
                      </template>
                      <HBadge v-else variant="default" size="sm">
                        {{ roleLabel(seat.role) }}
                      </HBadge>
                    </td>
                    <td class="py-3 pr-3">
                      <HBadge :variant="seat.is_active ? 'active' : 'idle'" size="sm">
                        {{ seat.is_active ? 'Active' : 'Inactive' }}
                      </HBadge>
                    </td>
                    <td class="py-3 pr-3 text-xs text-horus-text-muted">
                      {{ formatDate(seat.joined_at) }}
                    </td>
                    <td class="py-3 text-right">
                      <HButton
                        v-if="isOrgAdmin && seat.is_active"
                        variant="danger"
                        size="sm"
                        :loading="deactivatingSeatId === seat.id"
                        @click="deactivateSeat(seat)"
                      >
                        Deactivate
                      </HButton>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </HCard>

          <HCard variant="default" padding="md">
            <div class="mb-4">
              <h2 class="text-sm font-semibold text-horus-text-primary">Session Visibility</h2>
              <p class="text-xs text-horus-text-muted">
                Live and historical training sessions in organization scope.
              </p>
            </div>

            <div class="mb-3 flex items-center gap-2">
              <HBadge variant="active" size="sm">Active {{ activeSessionCount }}</HBadge>
              <HBadge variant="idle" size="sm">Completed {{ completedSessionCount }}</HBadge>
              <HBadge variant="default" size="sm">Total {{ sessions.length }}</HBadge>
            </div>

            <div v-if="recentSessions.length === 0" class="rounded-lg border border-white/10 p-4 text-center">
              <p class="text-sm text-horus-text-muted">No sessions available yet.</p>
            </div>

            <div v-else class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-horus-border-subtle text-left text-xxs uppercase tracking-wider text-horus-text-muted">
                    <th class="pb-2 pr-3">Session</th>
                    <th class="pb-2 pr-3">Status</th>
                    <th class="pb-2 pr-3">Scenario</th>
                    <th class="pb-2 pr-3">Started</th>
                    <th class="pb-2">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="session in recentSessions"
                    :key="session.id"
                    class="border-b border-horus-border-subtle/40"
                  >
                    <td class="py-3 pr-3 font-mono text-horus-text-primary">#{{ session.id }}</td>
                    <td class="py-3 pr-3">
                      <HBadge :variant="sessionStatusVariant(session.status)" size="sm">
                        {{ session.status }}
                      </HBadge>
                    </td>
                    <td class="py-3 pr-3 text-horus-text-secondary">
                      {{ session.scenario_id ? `#${session.scenario_id}` : '—' }}
                    </td>
                    <td class="py-3 pr-3 text-xs text-horus-text-muted">
                      {{ formatDate(session.started_at) }}
                    </td>
                    <td class="py-3 text-xs text-horus-text-muted">
                      {{ formatDuration(session) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </HCard>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
select option {
  background-color: #0a0f1a;
  color: #f8fafc;
}
</style>
