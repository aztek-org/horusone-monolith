<script setup lang="ts">
import type {
  OrganizationSummary,
  OrganizationUpdatePayload,
  SeatWithUser,
  SeatCreatePayload,
} from '~/composables/useAdmin'

definePageMeta({
  layout: 'admin',
  middleware: ['auth', 'admin'],
})

const route = useRoute()
const router = useRouter()
const admin = useAdmin()
const orgId = computed(() => route.params.id as string)

// ─── State ───────────────────────────────────────────────────────────────────
const org = ref<OrganizationSummary | null>(null)
const seats = ref<SeatWithUser[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

// Edit org
const isEditing = ref(false)
const editForm = ref<OrganizationUpdatePayload>({})
const isSaving = ref(false)
const saveError = ref<string | null>(null)

// Add seat
const showAddSeat = ref(false)
const seatForm = ref<SeatCreatePayload>({ email: '', role: 'student' })
const isAddingSeat = ref(false)
const addSeatError = ref<string | null>(null)

// Delete confirmation
const confirmDeleteOrg = ref(false)
const isDeleting = ref(false)

const roleOptions = [
  { value: 'student', label: 'Student' },
  { value: 'instructor', label: 'Instructor' },
  { value: 'org-admin', label: 'Org Admin' },
]

const activeSeats = computed(() => seats.value.filter(s => s.is_active))
const inactiveSeats = computed(() => seats.value.filter(s => !s.is_active))

// ─── Load Data ───────────────────────────────────────────────────────────────
async function loadData() {
  isLoading.value = true
  error.value = null
  try {
    const [orgData, seatsData] = await Promise.all([
      admin.fetchOrganization(orgId.value),
      admin.fetchSeats(orgId.value),
    ])
    org.value = orgData
    seats.value = seatsData
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load organization'
  }
  finally {
    isLoading.value = false
  }
}

// ─── Edit Organization ───────────────────────────────────────────────────────
function startEditing() {
  if (!org.value) return
  editForm.value = {
    name: org.value.name,
    slug: org.value.slug,
    max_seats: org.value.max_seats,
    is_active: org.value.is_active,
  }
  isEditing.value = true
  saveError.value = null
}

function cancelEditing() {
  isEditing.value = false
  saveError.value = null
}

async function saveOrg() {
  isSaving.value = true
  saveError.value = null
  try {
    org.value = await admin.updateOrganization(orgId.value, editForm.value)
    isEditing.value = false
  }
  catch (e) {
    saveError.value = e instanceof Error ? e.message : 'Failed to save changes'
  }
  finally {
    isSaving.value = false
  }
}

// ─── Delete Organization ─────────────────────────────────────────────────────
async function handleDeleteOrg() {
  isDeleting.value = true
  try {
    await admin.deleteOrganization(orgId.value)
    router.push('/admin/organizations')
  }
  catch {
    // Stay on page if delete fails
  }
  finally {
    isDeleting.value = false
    confirmDeleteOrg.value = false
  }
}

// ─── Seat Management ─────────────────────────────────────────────────────────
async function handleAddSeat() {
  isAddingSeat.value = true
  addSeatError.value = null
  try {
    const newSeat = await admin.createSeat(orgId.value, seatForm.value)
    seats.value.push(newSeat)
    showAddSeat.value = false
    seatForm.value = { email: '', role: 'student' }
  }
  catch (e) {
    addSeatError.value = e instanceof Error ? e.message : 'Failed to add seat'
  }
  finally {
    isAddingSeat.value = false
  }
}

async function toggleSeatActive(seat: SeatWithUser) {
  try {
    const updated = await admin.updateSeat(orgId.value, seat.id, {
      is_active: !seat.is_active,
    })
    const idx = seats.value.findIndex(s => s.id === seat.id)
    if (idx !== -1) seats.value[idx] = updated
  }
  catch {
    // Silent fail — could add toast notification
  }
}

async function changeSeatRole(seat: SeatWithUser, newRole: string) {
  try {
    const updated = await admin.updateSeat(orgId.value, seat.id, { role: newRole })
    const idx = seats.value.findIndex(s => s.id === seat.id)
    if (idx !== -1) seats.value[idx] = updated
  }
  catch {
    // Silent fail
  }
}

async function removeSeat(seat: SeatWithUser) {
  try {
    await admin.deleteSeat(orgId.value, seat.id)
    seats.value = seats.value.filter(s => s.id !== seat.id)
  }
  catch {
    // Silent fail
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6 max-w-5xl mx-auto">
    <!-- Back Link -->
    <NuxtLink
      to="/admin/organizations"
      class="inline-flex items-center gap-2 text-sm text-horus-text-muted hover:text-horus-text-primary transition-colors"
    >
      <Icon name="heroicons:arrow-left" class="w-4 h-4" />
      Back to Organizations
    </NuxtLink>

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

    <!-- Loading -->
    <template v-else-if="isLoading">
      <HCard variant="elevated" padding="lg">
        <div class="animate-pulse space-y-4">
          <div class="h-6 w-64 rounded bg-horus-bg-tertiary" />
          <div class="h-4 w-48 rounded bg-horus-bg-tertiary" />
          <div class="grid grid-cols-3 gap-4 mt-6">
            <div class="h-16 rounded bg-horus-bg-tertiary" />
            <div class="h-16 rounded bg-horus-bg-tertiary" />
            <div class="h-16 rounded bg-horus-bg-tertiary" />
          </div>
        </div>
      </HCard>
    </template>

    <!-- Organization Detail -->
    <template v-else-if="org">
      <!-- ── Org Header ────────────────────────────────────────────────────── -->
      <HCard variant="elevated" padding="lg">
        <template v-if="!isEditing">
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div class="flex items-start gap-4">
              <div class="w-12 h-12 rounded-xl bg-horus-accent-cyan/10 flex items-center justify-center flex-shrink-0">
                <Icon name="heroicons:building-office-2" class="w-6 h-6 text-horus-accent-cyan" />
              </div>
              <div>
                <div class="flex items-center gap-3">
                  <h1 class="text-xl font-bold text-horus-text-primary">{{ org.name }}</h1>
                  <HBadge :variant="org.is_active ? 'success' : 'danger'" size="sm">
                    {{ org.is_active ? 'Active' : 'Inactive' }}
                  </HBadge>
                </div>
                <p class="text-sm text-horus-text-muted font-mono mt-1">{{ org.slug }}</p>
                <p class="text-xs text-horus-text-muted mt-1">
                  Created {{ formatDate(org.created_at) }}
                </p>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <HButton variant="secondary" size="sm" icon="heroicons:pencil" @click="startEditing">
                Edit
              </HButton>
              <HButton
                variant="danger"
                size="sm"
                icon="heroicons:trash"
                @click="confirmDeleteOrg = true"
              >
                Delete
              </HButton>
            </div>
          </div>

          <!-- Stats -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-horus-border-subtle">
            <div>
              <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Max Seats</p>
              <p class="text-lg font-bold text-horus-text-primary mt-1">{{ org.max_seats }}</p>
            </div>
            <div>
              <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Active Seats</p>
              <p class="text-lg font-bold text-horus-accent-cyan mt-1">
                {{ org.active_seats }}<span class="text-sm text-horus-text-muted">/{{ org.max_seats }}</span>
              </p>
            </div>
            <div>
              <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Sessions</p>
              <p class="text-lg font-bold text-horus-text-primary mt-1">{{ org.total_sessions }}</p>
            </div>
            <div>
              <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Scenarios</p>
              <p class="text-lg font-bold text-horus-text-primary mt-1">{{ org.total_scenarios }}</p>
            </div>
          </div>
        </template>

        <!-- Edit Form -->
        <template v-else>
          <form class="space-y-4" @submit.prevent="saveOrg">
            <h2 class="text-lg font-semibold text-horus-text-primary">Edit Organization</h2>

            <div v-if="saveError" class="flex items-center gap-2 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/20">
              <Icon name="heroicons:exclamation-circle" class="w-4 h-4 text-horus-status-danger flex-shrink-0" />
              <p class="text-sm text-horus-status-danger">{{ saveError }}</p>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Name</label>
                <input
                  v-model="editForm.name"
                  type="text"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Slug</label>
                <input
                  v-model="editForm.slug"
                  type="text"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary font-mono focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Max Seats</label>
                <input
                  v-model.number="editForm.max_seats"
                  type="number"
                  min="1"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Status</label>
                <div class="flex items-center gap-3 h-[42px]">
                  <HCheckbox
                    :model-value="editForm.is_active ?? true"
                    label="Active"
                    @update:model-value="editForm.is_active = $event"
                  />
                </div>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-2">
              <HButton variant="ghost" size="sm" type="button" @click="cancelEditing">
                Cancel
              </HButton>
              <HButton variant="primary" size="sm" type="submit" :loading="isSaving" icon="heroicons:check">
                Save Changes
              </HButton>
            </div>
          </form>
        </template>
      </HCard>

      <!-- ── Seat Management ───────────────────────────────────────────────── -->
      <HSection title="Seat Management" icon="heroicons:users">
        <!-- Add Seat Button -->
        <div class="flex justify-end mb-3">
          <HButton
            variant="secondary"
            size="sm"
            icon="heroicons:user-plus"
            @click="showAddSeat = !showAddSeat"
          >
            Add Seat
          </HButton>
        </div>

        <!-- Add Seat Form -->
        <Transition
          enter-active-class="transition-all duration-200"
          enter-from-class="opacity-0 -translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-150"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 -translate-y-2"
        >
          <HCard v-if="showAddSeat" variant="elevated" padding="md" class="mb-4">
            <form class="space-y-4" @submit.prevent="handleAddSeat">
              <h3 class="text-sm font-semibold text-horus-text-primary">Add New Seat</h3>

              <div v-if="addSeatError" class="flex items-center gap-2 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/20">
                <Icon name="heroicons:exclamation-circle" class="w-4 h-4 text-horus-status-danger flex-shrink-0" />
                <p class="text-sm text-horus-status-danger">{{ addSeatError }}</p>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div class="sm:col-span-2 space-y-1.5">
                  <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Email</label>
                  <input
                    v-model="seatForm.email"
                    type="email"
                    required
                    placeholder="user@example.com"
                    class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                  />
                </div>
                <HDropdown
                  v-model="seatForm.role"
                  :options="roleOptions"
                  label="Role"
                />
              </div>

              <div class="flex justify-end gap-3">
                <HButton variant="ghost" size="sm" type="button" @click="showAddSeat = false">
                  Cancel
                </HButton>
                <HButton variant="primary" size="sm" type="submit" :loading="isAddingSeat" icon="heroicons:user-plus">
                  Add Seat
                </HButton>
              </div>
            </form>
          </HCard>
        </Transition>

        <!-- Seats Table -->
        <HCard variant="elevated" padding="none">
          <div v-if="seats.length === 0" class="py-8 text-center">
            <Icon name="heroicons:users" class="w-10 h-10 text-horus-text-muted mx-auto mb-2" />
            <p class="text-sm text-horus-text-muted">No seats assigned yet</p>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b border-horus-border-subtle">
                  <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                    User
                  </th>
                  <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                    Role
                  </th>
                  <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden md:table-cell">
                    Status
                  </th>
                  <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden md:table-cell">
                    Joined
                  </th>
                  <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="seat in [...activeSeats, ...inactiveSeats]"
                  :key="seat.id"
                  :class="[
                    'border-b border-horus-border-subtle last:border-0 transition-colors',
                    !seat.is_active && 'opacity-50'
                  ]"
                >
                  <td class="px-4 py-3">
                    <div class="min-w-0">
                      <p class="text-sm font-medium text-horus-text-primary truncate">
                        {{ seat.user.display_name || '—' }}
                      </p>
                      <p class="text-xs text-horus-text-muted truncate">{{ seat.user.email }}</p>
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <select
                      :value="seat.role"
                      class="bg-horus-bg-secondary border border-horus-border-subtle rounded-md px-2 py-1 text-xs text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan appearance-none cursor-pointer"
                      @change="changeSeatRole(seat, ($event.target as HTMLSelectElement).value)"
                    >
                      <option v-for="opt in roleOptions" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                      </option>
                    </select>
                  </td>
                  <td class="px-4 py-3 text-center hidden md:table-cell">
                    <HBadge :variant="seat.is_active ? 'success' : 'idle'" size="sm">
                      {{ seat.is_active ? 'Active' : 'Inactive' }}
                    </HBadge>
                  </td>
                  <td class="px-4 py-3 text-right hidden md:table-cell">
                    <span class="text-xs text-horus-text-muted">{{ formatDate(seat.joined_at) }}</span>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                        :title="seat.is_active ? 'Deactivate' : 'Activate'"
                        @click="toggleSeatActive(seat)"
                      >
                        <Icon
                          :name="seat.is_active ? 'heroicons:pause-circle' : 'heroicons:play-circle'"
                          class="w-4 h-4"
                        />
                      </button>
                      <button
                        class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-status-danger hover:bg-horus-status-danger/10 transition-colors"
                        title="Remove seat"
                        @click="removeSeat(seat)"
                      >
                        <Icon name="heroicons:trash" class="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </HCard>
      </HSection>
    </template>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-200"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="confirmDeleteOrg"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="confirmDeleteOrg = false" />

          <div class="relative w-full max-w-sm bg-horus-bg-elevated border border-horus-border-subtle rounded-xl shadow-2xl animate-slide-up">
            <div class="p-6 text-center space-y-4">
              <div class="w-12 h-12 rounded-full bg-horus-status-danger/10 flex items-center justify-center mx-auto">
                <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 text-horus-status-danger" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-horus-text-primary">Delete Organization?</h3>
                <p class="text-sm text-horus-text-muted mt-2">
                  This will deactivate <strong class="text-horus-text-primary">{{ org?.name }}</strong> and all associated seats.
                </p>
              </div>
              <div class="flex justify-center gap-3 pt-2">
                <HButton variant="ghost" size="sm" @click="confirmDeleteOrg = false">
                  Cancel
                </HButton>
                <HButton variant="danger" size="sm" :loading="isDeleting" icon="heroicons:trash" @click="handleDeleteOrg">
                  Delete
                </HButton>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
