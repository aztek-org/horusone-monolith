<script setup lang="ts">
import type { OrganizationSummary, OrganizationCreatePayload } from '~/composables/useAdmin'

definePageMeta({
  layout: 'admin',
  middleware: ['auth', 'admin'],
})

const admin = useAdmin()
const router = useRouter()

const organizations = ref<OrganizationSummary[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')
const showCreateModal = ref(false)

// Create form state
const createForm = ref<OrganizationCreatePayload>({
  name: '',
  slug: '',
  max_seats: 10,
})
const isCreating = ref(false)
const createError = ref<string | null>(null)

const filteredOrganizations = computed(() => {
  if (!searchQuery.value.trim()) return organizations.value
  const q = searchQuery.value.toLowerCase()
  return organizations.value.filter(
    org => org.name.toLowerCase().includes(q) || org.slug.toLowerCase().includes(q),
  )
})

async function loadOrganizations() {
  isLoading.value = true
  error.value = null
  try {
    organizations.value = await admin.fetchOrganizations()
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load organizations'
  }
  finally {
    isLoading.value = false
  }
}

function autoSlug() {
  createForm.value.slug = createForm.value.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

async function handleCreate() {
  isCreating.value = true
  createError.value = null
  try {
    await admin.createOrganization(createForm.value)
    showCreateModal.value = false
    createForm.value = { name: '', slug: '', max_seats: 10 }
    await loadOrganizations()
  }
  catch (e) {
    createError.value = e instanceof Error ? e.message : 'Failed to create organization'
  }
  finally {
    isCreating.value = false
  }
}

function navigateToOrg(orgId: string) {
  router.push(`/admin/organizations/${orgId}`)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(loadOrganizations)
</script>

<template>
  <div class="space-y-6 max-w-7xl mx-auto">
    <!-- Page Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-horus-text-primary">Organizations</h1>
        <p class="text-sm text-horus-text-secondary mt-1">
          Manage training organizations and seat allocations
        </p>
      </div>
      <HButton
        variant="primary"
        size="sm"
        icon="heroicons:plus"
        @click="showCreateModal = true"
      >
        New Organization
      </HButton>
    </div>

    <!-- Search -->
    <div class="relative max-w-md">
      <Icon
        name="heroicons:magnifying-glass"
        class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-horus-text-muted"
      />
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search by name or slug..."
        class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg pl-10 pr-4 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
      />
    </div>

    <!-- Error State -->
    <HCard v-if="error" variant="elevated" padding="lg">
      <div class="flex items-center gap-3 text-horus-status-danger">
        <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 flex-shrink-0" />
        <div class="flex-1">
          <p class="font-medium">{{ error }}</p>
        </div>
        <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadOrganizations">
          Retry
        </HButton>
      </div>
    </HCard>

    <!-- Loading -->
    <div v-else-if="isLoading" class="space-y-3">
      <HCard v-for="n in 4" :key="n" variant="elevated" padding="md">
        <div class="animate-pulse flex items-center gap-4">
          <div class="w-10 h-10 rounded-lg bg-horus-bg-tertiary" />
          <div class="flex-1 space-y-2">
            <div class="h-4 w-48 rounded bg-horus-bg-tertiary" />
            <div class="h-3 w-32 rounded bg-horus-bg-tertiary" />
          </div>
          <div class="h-6 w-16 rounded bg-horus-bg-tertiary" />
        </div>
      </HCard>
    </div>

    <!-- Organizations Table -->
    <template v-else>
      <!-- Empty State -->
      <HCard v-if="filteredOrganizations.length === 0" variant="elevated" padding="lg">
        <div class="py-8 text-center">
          <Icon name="heroicons:building-office-2" class="w-12 h-12 text-horus-text-muted mx-auto mb-3" />
          <p class="text-horus-text-secondary font-medium">
            {{ searchQuery ? 'No organizations match your search' : 'No organizations yet' }}
          </p>
          <p class="text-sm text-horus-text-muted mt-1">
            {{ searchQuery ? 'Try adjusting your search term' : 'Create your first organization to get started' }}
          </p>
        </div>
      </HCard>

      <!-- Table -->
      <HCard v-else variant="elevated" padding="none">
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-horus-border-subtle">
                <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                  Organization
                </th>
                <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden md:table-cell">
                  Status
                </th>
                <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden lg:table-cell">
                  Seats
                </th>
                <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden lg:table-cell">
                  Sessions
                </th>
                <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden xl:table-cell">
                  Scenarios
                </th>
                <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden md:table-cell">
                  Created
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="org in filteredOrganizations"
                :key="org.id"
                class="border-b border-horus-border-subtle last:border-0 hover:bg-horus-bg-tertiary/50 cursor-pointer transition-colors"
                @click="navigateToOrg(org.id)"
              >
                <td class="px-4 py-3">
                  <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-lg bg-horus-accent-cyan/10 flex items-center justify-center flex-shrink-0">
                      <Icon name="heroicons:building-office-2" class="w-4 h-4 text-horus-accent-cyan" />
                    </div>
                    <div class="min-w-0">
                      <p class="text-sm font-medium text-horus-text-primary truncate">{{ org.name }}</p>
                      <p class="text-xs text-horus-text-muted font-mono">{{ org.slug }}</p>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 hidden md:table-cell">
                  <HBadge :variant="org.is_active ? 'success' : 'danger'" size="sm">
                    {{ org.is_active ? 'Active' : 'Inactive' }}
                  </HBadge>
                </td>
                <td class="px-4 py-3 text-center hidden lg:table-cell">
                  <span class="text-sm text-horus-text-primary">{{ org.active_seats }}</span>
                  <span class="text-xs text-horus-text-muted">/{{ org.max_seats }}</span>
                </td>
                <td class="px-4 py-3 text-center hidden lg:table-cell">
                  <span class="text-sm text-horus-text-primary">{{ org.total_sessions }}</span>
                </td>
                <td class="px-4 py-3 text-center hidden xl:table-cell">
                  <span class="text-sm text-horus-text-primary">{{ org.total_scenarios }}</span>
                </td>
                <td class="px-4 py-3 text-right hidden md:table-cell">
                  <span class="text-xs text-horus-text-muted">{{ formatDate(org.created_at) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </HCard>
    </template>

    <!-- Create Organization Modal -->
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
          v-if="showCreateModal"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <!-- Backdrop -->
          <div
            class="absolute inset-0 bg-black/60 backdrop-blur-sm"
            @click="showCreateModal = false"
          />

          <!-- Modal -->
          <div class="relative w-full max-w-md bg-horus-bg-elevated border border-horus-border-subtle rounded-xl shadow-2xl animate-slide-up">
            <!-- Header -->
            <div class="flex items-center justify-between p-5 border-b border-horus-border-subtle">
              <h3 class="text-lg font-semibold text-horus-text-primary">New Organization</h3>
              <button
                class="p-1.5 rounded-lg text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                @click="showCreateModal = false"
              >
                <Icon name="heroicons:x-mark" class="w-5 h-5" />
              </button>
            </div>

            <!-- Form -->
            <form class="p-5 space-y-4" @submit.prevent="handleCreate">
              <!-- Error -->
              <div v-if="createError" class="flex items-center gap-2 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/20">
                <Icon name="heroicons:exclamation-circle" class="w-4 h-4 text-horus-status-danger flex-shrink-0" />
                <p class="text-sm text-horus-status-danger">{{ createError }}</p>
              </div>

              <!-- Name -->
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
                  Organization Name
                </label>
                <input
                  v-model="createForm.name"
                  type="text"
                  required
                  placeholder="e.g. Tokyo Flight Academy"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                  @input="autoSlug"
                />
              </div>

              <!-- Slug -->
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
                  Slug
                </label>
                <input
                  v-model="createForm.slug"
                  type="text"
                  required
                  placeholder="tokyo-flight-academy"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary font-mono placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>

              <!-- Max Seats -->
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">
                  Max Seats
                </label>
                <input
                  v-model.number="createForm.max_seats"
                  type="number"
                  required
                  min="1"
                  max="9999"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>

              <!-- Actions -->
              <div class="flex justify-end gap-3 pt-2">
                <HButton
                  variant="ghost"
                  size="sm"
                  type="button"
                  @click="showCreateModal = false"
                >
                  Cancel
                </HButton>
                <HButton
                  variant="primary"
                  size="sm"
                  type="submit"
                  :loading="isCreating"
                  icon="heroicons:plus"
                >
                  Create
                </HButton>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
