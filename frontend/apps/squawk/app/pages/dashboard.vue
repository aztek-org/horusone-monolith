<script setup lang="ts">
defineOptions({
  name: 'SquawkDashboardPage',
})

definePageMeta({
  layout: false,
  middleware: 'auth',
})

interface PlatformStats {
  total_orgs: number
  total_users: number
  total_sessions: number
  total_scenarios: number
}

type BillingPlan = 'starter' | 'growth' | 'enterprise'
type BillingStatus = 'trial' | 'active' | 'past_due' | 'suspended' | 'canceled'
type BillingCycle = 'monthly' | 'yearly'

interface BillingDraft {
  billing_plan: BillingPlan
  billing_status: BillingStatus
  billing_cycle: BillingCycle
}

interface OrganizationSummary {
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

interface AdminUser {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

interface OrganizationLeaderboardEntry {
  organization_id: string
  organization_name: string
  organization_slug: string
  is_active: boolean
  total_sessions: number
  completed_sessions: number
  active_sessions: number
  active_seats: number
  completion_rate: number
}

const { user, logout, hasRole } = useAuth()
const api = useApi()

const isPlatformAdmin = computed(() => hasRole('platform-admin'))

const stats = ref<PlatformStats | null>(null)
const organizations = ref<OrganizationSummary[]>([])
const users = ref<AdminUser[]>([])
const organizationLeaderboard = ref<OrganizationLeaderboardEntry[]>([])

const isLoading = ref(true)
const isLoadingUsers = ref(false)
const isLoadingLeaderboard = ref(false)
const pageError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const actionSuccess = ref<string | null>(null)

const orgName = ref('')
const orgSlug = ref('')
const orgMaxSeats = ref(50)
const orgBillingPlan = ref<BillingPlan>('starter')
const orgBillingStatus = ref<BillingStatus>('trial')
const orgBillingCycle = ref<BillingCycle>('monthly')
const isCreatingOrg = ref(false)
const savingOrgId = ref<string | null>(null)
const deactivatingOrgId = ref<string | null>(null)
const togglingUserId = ref<string | null>(null)
const userSearch = ref('')
const maxSeatDrafts = ref<Record<string, number>>({})
const billingDrafts = ref<Record<string, BillingDraft>>({})

const activeOrganizations = computed(() =>
  organizations.value.filter(org => org.is_active).length,
)

const inactiveOrganizations = computed(() =>
  organizations.value.filter(org => !org.is_active).length,
)

const billingPlanOptions: BillingPlan[] = ['starter', 'growth', 'enterprise']
const billingStatusOptions: BillingStatus[] = ['trial', 'active', 'past_due', 'suspended', 'canceled']
const billingCycleOptions: BillingCycle[] = ['monthly', 'yearly']

function clearActionBanners() {
  actionError.value = null
  actionSuccess.value = null
}

function setActionError(err: unknown, fallback: string) {
  const apiErr = err as { detail?: string }
  actionError.value = apiErr.detail ?? fallback
  actionSuccess.value = null
}

function slugify(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

function fillSlugFromName() {
  orgSlug.value = slugify(orgName.value)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatCompletionRate(rate: number): string {
  return `${Math.round(rate)}%`
}

function resetOrgForm() {
  orgName.value = ''
  orgSlug.value = ''
  orgMaxSeats.value = 50
  orgBillingPlan.value = 'starter'
  orgBillingStatus.value = 'trial'
  orgBillingCycle.value = 'monthly'
}

function statusVariant(isActive: boolean): 'active' | 'idle' {
  return isActive ? 'active' : 'idle'
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

function billingCycleLabel(cycle: BillingCycle): string {
  return cycle === 'monthly' ? 'Monthly' : 'Yearly'
}

function billingStatusVariant(status: BillingStatus): 'active' | 'warning' | 'danger' | 'idle' {
  if (status === 'active') return 'active'
  if (status === 'trial') return 'idle'
  if (status === 'past_due') return 'warning'
  return 'danger'
}

function organizationSeatUsage(org: OrganizationSummary): number {
  if (org.max_seats <= 0) return 0
  return Math.min(100, Math.round((org.seat_count / org.max_seats) * 100))
}

function canSaveMaxSeats(org: OrganizationSummary): boolean {
  const draft = maxSeatDrafts.value[org.id]
  return draft !== undefined && Number.isFinite(draft) && draft > 0 && draft !== org.max_seats
}

async function loadStats() {
  stats.value = await api.get<PlatformStats>('/api/v1/admin/stats')
}

async function loadOrganizations() {
  organizations.value = await api.get<OrganizationSummary[]>('/api/v1/admin/organizations/?limit=100')
  maxSeatDrafts.value = Object.fromEntries(
    organizations.value.map(org => [org.id, org.max_seats]),
  )
  billingDrafts.value = Object.fromEntries(
    organizations.value.map(org => [
      org.id,
      {
        billing_plan: normalizeBillingPlan(org.billing_plan),
        billing_status: normalizeBillingStatus(org.billing_status),
        billing_cycle: normalizeBillingCycle(org.billing_cycle),
      },
    ]),
  )
}

async function loadUsers(searchTerm: string = userSearch.value) {
  isLoadingUsers.value = true
  try {
    const query = new URLSearchParams({ limit: '50' })
    if (searchTerm.trim()) {
      query.set('search', searchTerm.trim())
    }
    users.value = await api.get<AdminUser[]>(`/api/v1/admin/users/?${query.toString()}`)
  }
  finally {
    isLoadingUsers.value = false
  }
}

async function loadOrganizationLeaderboard() {
  isLoadingLeaderboard.value = true
  try {
    organizationLeaderboard.value = await api.get<OrganizationLeaderboardEntry[]>(
      '/api/v1/analytics/platform-org-leaderboard?limit=8',
    )
  }
  finally {
    isLoadingLeaderboard.value = false
  }
}

async function loadDashboardData() {
  if (!isPlatformAdmin.value) {
    isLoading.value = false
    pageError.value = 'This account does not have Squawk platform-admin access.'
    return
  }

  isLoading.value = true
  pageError.value = null

  try {
    await Promise.all([loadStats(), loadOrganizations(), loadUsers(''), loadOrganizationLeaderboard()])
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    pageError.value = apiErr.detail ?? 'Failed to load Squawk platform data'
  }
  finally {
    isLoading.value = false
  }
}

async function createOrganization() {
  if (!isPlatformAdmin.value || isCreatingOrg.value) return
  if (!orgName.value.trim() || !orgSlug.value.trim()) {
    actionError.value = 'Organization name and slug are required.'
    actionSuccess.value = null
    return
  }

  isCreatingOrg.value = true
  clearActionBanners()
  try {
    await api.post('/api/v1/admin/organizations/', {
      name: orgName.value.trim(),
      slug: orgSlug.value.trim(),
      max_seats: Number(orgMaxSeats.value),
      billing_plan: orgBillingPlan.value,
      billing_status: orgBillingStatus.value,
      billing_cycle: orgBillingCycle.value,
    })
    actionSuccess.value = `Organization ${orgName.value.trim()} created.`
    resetOrgForm()
    await Promise.all([loadStats(), loadOrganizations()])
  }
  catch (err) {
    setActionError(err, 'Failed to create organization')
  }
  finally {
    isCreatingOrg.value = false
  }
}

async function saveMaxSeats(org: OrganizationSummary) {
  if (!isPlatformAdmin.value || savingOrgId.value) return
  const draft = maxSeatDrafts.value[org.id]
  if (draft === undefined || !Number.isFinite(draft) || draft <= 0 || draft === org.max_seats) return

  savingOrgId.value = org.id
  clearActionBanners()

  try {
    const updated = await api.put<OrganizationSummary>(`/api/v1/admin/organizations/${org.id}`, {
      max_seats: Number(draft),
    })
    org.max_seats = updated.max_seats
    maxSeatDrafts.value[org.id] = updated.max_seats
    actionSuccess.value = `${org.name} max seats updated to ${updated.max_seats}.`
  }
  catch (err) {
    setActionError(err, `Failed to update max seats for ${org.name}`)
  }
  finally {
    savingOrgId.value = null
  }
}

function canSaveBilling(org: OrganizationSummary): boolean {
  const draft = billingDrafts.value[org.id]
  if (!draft) return false
  return (
    draft.billing_plan !== org.billing_plan
    || draft.billing_status !== org.billing_status
    || draft.billing_cycle !== org.billing_cycle
  )
}

async function saveBilling(org: OrganizationSummary) {
  if (!isPlatformAdmin.value || savingOrgId.value) return
  const draft = billingDrafts.value[org.id]
  if (!draft || !canSaveBilling(org)) return

  savingOrgId.value = org.id
  clearActionBanners()
  try {
    const updated = await api.put<OrganizationSummary>(`/api/v1/admin/organizations/${org.id}`, {
      billing_plan: draft.billing_plan,
      billing_status: draft.billing_status,
      billing_cycle: draft.billing_cycle,
    })
    org.billing_plan = updated.billing_plan
    org.billing_status = updated.billing_status
    org.billing_cycle = updated.billing_cycle
    billingDrafts.value[org.id] = {
      billing_plan: normalizeBillingPlan(updated.billing_plan),
      billing_status: normalizeBillingStatus(updated.billing_status),
      billing_cycle: normalizeBillingCycle(updated.billing_cycle),
    }
    actionSuccess.value = `${org.name} billing profile updated.`
  }
  catch (err) {
    setActionError(err, `Failed to update billing for ${org.name}`)
  }
  finally {
    savingOrgId.value = null
  }
}

async function deactivateOrganization(org: OrganizationSummary) {
  if (!isPlatformAdmin.value || !org.is_active || deactivatingOrgId.value) return
  if (!window.confirm(`Deactivate organization ${org.name}?`)) return

  deactivatingOrgId.value = org.id
  clearActionBanners()
  try {
    await api.del(`/api/v1/admin/organizations/${org.id}`)
    actionSuccess.value = `${org.name} was deactivated.`
    await Promise.all([loadStats(), loadOrganizations()])
  }
  catch (err) {
    setActionError(err, `Failed to deactivate ${org.name}`)
  }
  finally {
    deactivatingOrgId.value = null
  }
}

async function toggleUserStatus(targetUser: AdminUser) {
  if (!isPlatformAdmin.value || togglingUserId.value) return
  togglingUserId.value = targetUser.id
  clearActionBanners()
  try {
    const updated = await api.put<AdminUser>(`/api/v1/admin/users/${targetUser.id}`, {
      is_active: !targetUser.is_active,
    })
    targetUser.is_active = updated.is_active
    actionSuccess.value = `${targetUser.email} is now ${updated.is_active ? 'active' : 'inactive'}.`
  }
  catch (err) {
    setActionError(err, `Failed to update ${targetUser.email}`)
  }
  finally {
    togglingUserId.value = null
  }
}

onMounted(() => {
  loadDashboardData()
})
</script>

<template>
  <div class="min-h-screen bg-horus-bg-primary px-4 py-6 lg:px-8">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <header class="rounded-xl border border-white/10 bg-horus-bg-secondary p-5 lg:p-6">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 class="text-2xl font-semibold text-horus-text-primary">Squawk Platform Dashboard</h1>
            <p class="mt-1 text-sm text-horus-text-secondary">
              Platform-admin oversight of organizations, users, and operational metrics.
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
        v-if="!isPlatformAdmin"
        class="rounded-xl border border-horus-status-warning/40 bg-horus-status-warning/10 p-4"
      >
        <p class="text-sm text-horus-status-warning">
          Squawk requires platform-admin role.
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
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Organizations</p>
            <p class="mt-2 text-2xl font-semibold text-horus-text-primary">{{ stats?.total_orgs ?? 0 }}</p>
            <p class="text-xs text-horus-text-muted">
              {{ activeOrganizations }} active · {{ inactiveOrganizations }} inactive
            </p>
          </HCard>

          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Users</p>
            <p class="mt-2 text-2xl font-semibold text-horus-text-primary">{{ stats?.total_users ?? 0 }}</p>
            <p class="text-xs text-horus-text-muted">Platform identity footprint</p>
          </HCard>

          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Sessions</p>
            <p class="mt-2 text-2xl font-semibold text-horus-text-primary">{{ stats?.total_sessions ?? 0 }}</p>
            <p class="text-xs text-horus-text-muted">Recorded training sessions</p>
          </HCard>

          <HCard variant="default" padding="md">
            <p class="text-xxs uppercase tracking-wider text-horus-text-muted">Scenarios</p>
            <p class="mt-2 text-2xl font-semibold text-horus-text-primary">{{ stats?.total_scenarios ?? 0 }}</p>
            <p class="text-xs text-horus-text-muted">Global scenario catalog</p>
          </HCard>
        </div>

        <HCard variant="default" padding="md">
          <div class="mb-4">
            <h2 class="text-sm font-semibold text-horus-text-primary">Organization Progress Leaderboard</h2>
            <p class="text-xs text-horus-text-muted">
              Ranked by completed training sessions across organizations.
            </p>
          </div>

          <div v-if="isLoadingLeaderboard" class="flex items-center justify-center py-10">
            <Icon name="svg-spinners:ring-resize" class="h-6 w-6 text-horus-accent-cyan" />
          </div>

          <div v-else-if="organizationLeaderboard.length === 0" class="rounded-lg border border-white/10 p-4 text-center">
            <p class="text-sm text-horus-text-muted">No organization leaderboard data yet.</p>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-horus-border-subtle text-left text-xxs uppercase tracking-wider text-horus-text-muted">
                  <th class="pb-2 pr-3">Organization</th>
                  <th class="pb-2 pr-3">Completed</th>
                  <th class="pb-2 pr-3">Active</th>
                  <th class="pb-2 pr-3">Seats</th>
                  <th class="pb-2 pr-3">Completion Rate</th>
                  <th class="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="entry in organizationLeaderboard"
                  :key="entry.organization_id"
                  class="border-b border-horus-border-subtle/40"
                >
                  <td class="py-3 pr-3">
                    <p class="font-medium text-horus-text-primary">{{ entry.organization_name }}</p>
                    <p class="text-xs text-horus-text-muted">{{ entry.organization_slug }}</p>
                  </td>
                  <td class="py-3 pr-3 text-horus-text-secondary">{{ entry.completed_sessions }}</td>
                  <td class="py-3 pr-3 text-horus-text-secondary">{{ entry.active_sessions }}</td>
                  <td class="py-3 pr-3 text-horus-text-secondary">{{ entry.active_seats }}</td>
                  <td class="py-3 pr-3">
                    <HBadge variant="info" size="sm">{{ formatCompletionRate(entry.completion_rate) }}</HBadge>
                  </td>
                  <td class="py-3">
                    <HBadge :variant="statusVariant(entry.is_active)" size="sm">
                      {{ entry.is_active ? 'Active' : 'Inactive' }}
                    </HBadge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </HCard>

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

        <div class="grid gap-6 lg:grid-cols-2">
          <HCard variant="default" padding="md">
            <div class="mb-4">
              <h2 class="text-sm font-semibold text-horus-text-primary">Organization Oversight</h2>
              <p class="text-xs text-horus-text-muted">
                Create organizations, adjust seat limits, and deactivate orgs.
              </p>
            </div>

            <div class="mb-4 rounded-lg border border-white/10 bg-horus-bg-tertiary/40 p-3">
              <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-horus-text-secondary">
                Create Organization
              </p>
              <div class="grid gap-2 sm:grid-cols-2">
                <input
                  v-model="orgName"
                  type="text"
                  placeholder="Organization name"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <div class="flex gap-2">
                  <input
                    v-model="orgSlug"
                    type="text"
                    placeholder="slug"
                    class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                  >
                  <HButton variant="secondary" size="sm" @click="fillSlugFromName">
                    Slug
                  </HButton>
                </div>
                <input
                  v-model.number="orgMaxSeats"
                  type="number"
                  min="1"
                  max="10000"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                <select
                  v-model="orgBillingPlan"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="plan in billingPlanOptions" :key="plan" :value="plan">
                    {{ billingPlanLabel(plan) }} plan
                  </option>
                </select>
                <select
                  v-model="orgBillingStatus"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="status in billingStatusOptions" :key="status" :value="status">
                    {{ billingStatusLabel(status) }}
                  </option>
                </select>
                <select
                  v-model="orgBillingCycle"
                  class="rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                >
                  <option v-for="cycle in billingCycleOptions" :key="cycle" :value="cycle">
                    {{ billingCycleLabel(cycle) }}
                  </option>
                </select>
                <HButton
                  variant="primary"
                  size="sm"
                  icon="heroicons:building-office-2"
                  class="sm:col-span-2"
                  :loading="isCreatingOrg"
                  @click="createOrganization"
                >
                  Create
                </HButton>
              </div>
            </div>

            <div v-if="organizations.length === 0" class="rounded-lg border border-white/10 p-4 text-center">
              <p class="text-sm text-horus-text-muted">No organizations found.</p>
            </div>

            <div v-else class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-horus-border-subtle text-left text-xxs uppercase tracking-wider text-horus-text-muted">
                    <th class="pb-2 pr-3">Organization</th>
                    <th class="pb-2 pr-3">Seats</th>
                    <th class="pb-2 pr-3">Billing</th>
                    <th class="pb-2 pr-3">Active Sessions</th>
                    <th class="pb-2 pr-3">Created</th>
                    <th class="pb-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="org in organizations"
                    :key="org.id"
                    class="border-b border-horus-border-subtle/40 align-top"
                  >
                    <td class="py-3 pr-3">
                      <p class="font-medium text-horus-text-primary">{{ org.name }}</p>
                      <p class="text-xs text-horus-text-muted">{{ org.slug }}</p>
                      <HBadge :variant="statusVariant(org.is_active)" size="sm" class="mt-1">
                        {{ org.is_active ? 'Active' : 'Inactive' }}
                      </HBadge>
                    </td>
                    <td class="py-3 pr-3">
                      <div class="min-w-[180px] space-y-2">
                        <p class="text-xs text-horus-text-secondary">
                          {{ org.seat_count }} / {{ org.max_seats }}
                        </p>
                        <HProgress :value="organizationSeatUsage(org)" :show-percentage="false" size="sm" />
                        <div class="flex items-center gap-2">
                          <input
                            v-model.number="maxSeatDrafts[org.id]"
                            type="number"
                            min="1"
                            max="10000"
                            class="w-24 rounded-md border border-white/15 bg-horus-bg-primary px-2 py-1 text-xs text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                          >
                          <HButton
                            variant="secondary"
                            size="sm"
                            :disabled="!canSaveMaxSeats(org)"
                            :loading="savingOrgId === org.id"
                            @click="saveMaxSeats(org)"
                          >
                            Save
                          </HButton>
                        </div>
                      </div>
                    </td>
                    <td class="py-3 pr-3">
                      <div class="min-w-[220px] space-y-2">
                        <div class="flex flex-wrap gap-1">
                          <HBadge variant="info" size="sm">{{ billingPlanLabel(org.billing_plan) }}</HBadge>
                          <HBadge :variant="billingStatusVariant(org.billing_status)" size="sm">
                            {{ billingStatusLabel(org.billing_status) }}
                          </HBadge>
                          <HBadge variant="default" size="sm">{{ billingCycleLabel(org.billing_cycle) }}</HBadge>
                        </div>
                        <div class="grid gap-2 sm:grid-cols-3">
                          <select
                            v-model="billingDrafts[org.id]!.billing_plan"
                            class="rounded-md border border-white/15 bg-horus-bg-primary px-2 py-1 text-xs text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                          >
                            <option v-for="plan in billingPlanOptions" :key="plan" :value="plan">
                              {{ billingPlanLabel(plan) }}
                            </option>
                          </select>
                          <select
                            v-model="billingDrafts[org.id]!.billing_status"
                            class="rounded-md border border-white/15 bg-horus-bg-primary px-2 py-1 text-xs text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                          >
                            <option v-for="status in billingStatusOptions" :key="status" :value="status">
                              {{ billingStatusLabel(status) }}
                            </option>
                          </select>
                          <select
                            v-model="billingDrafts[org.id]!.billing_cycle"
                            class="rounded-md border border-white/15 bg-horus-bg-primary px-2 py-1 text-xs text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
                          >
                            <option v-for="cycle in billingCycleOptions" :key="cycle" :value="cycle">
                              {{ billingCycleLabel(cycle) }}
                            </option>
                          </select>
                        </div>
                        <HButton
                          variant="secondary"
                          size="sm"
                          :disabled="!canSaveBilling(org)"
                          :loading="savingOrgId === org.id"
                          @click="saveBilling(org)"
                        >
                          Save Billing
                        </HButton>
                      </div>
                    </td>
                    <td class="py-3 pr-3 text-xs text-horus-text-secondary">
                      <p>{{ org.active_sessions }} active</p>
                      <p>{{ org.scenario_count }} scenarios</p>
                    </td>
                    <td class="py-3 pr-3 text-xs text-horus-text-muted">
                      {{ formatDate(org.created_at) }}
                    </td>
                    <td class="py-3 text-right">
                      <HButton
                        v-if="org.is_active"
                        variant="danger"
                        size="sm"
                        :loading="deactivatingOrgId === org.id"
                        @click="deactivateOrganization(org)"
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
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-horus-text-primary">User Directory</h2>
                <p class="text-xs text-horus-text-muted">
                  Platform-level user visibility and account activation control.
                </p>
              </div>
            </div>

            <div class="mb-4 flex items-center gap-2">
              <input
                v-model="userSearch"
                type="text"
                placeholder="Search by email"
                class="w-full rounded-md border border-white/15 bg-horus-bg-primary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
              >
              <HButton variant="secondary" size="sm" :loading="isLoadingUsers" @click="loadUsers()">
                Search
              </HButton>
            </div>

            <div v-if="users.length === 0" class="rounded-lg border border-white/10 p-4 text-center">
              <p class="text-sm text-horus-text-muted">No users found for current filter.</p>
            </div>

            <div v-else class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-horus-border-subtle text-left text-xxs uppercase tracking-wider text-horus-text-muted">
                    <th class="pb-2 pr-3">User</th>
                    <th class="pb-2 pr-3">Status</th>
                    <th class="pb-2 pr-3">Created</th>
                    <th class="pb-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="targetUser in users"
                    :key="targetUser.id"
                    class="border-b border-horus-border-subtle/40"
                  >
                    <td class="py-3 pr-3">
                      <p class="font-medium text-horus-text-primary">{{ targetUser.display_name }}</p>
                      <p class="text-xs text-horus-text-muted">{{ targetUser.email }}</p>
                    </td>
                    <td class="py-3 pr-3">
                      <HBadge :variant="statusVariant(targetUser.is_active)" size="sm">
                        {{ targetUser.is_active ? 'Active' : 'Inactive' }}
                      </HBadge>
                    </td>
                    <td class="py-3 pr-3 text-xs text-horus-text-muted">
                      {{ formatDate(targetUser.created_at) }}
                    </td>
                    <td class="py-3 text-right">
                      <HButton
                        variant="secondary"
                        size="sm"
                        :loading="togglingUserId === targetUser.id"
                        @click="toggleUserStatus(targetUser)"
                      >
                        {{ targetUser.is_active ? 'Disable' : 'Enable' }}
                      </HButton>
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
