<script setup lang="ts">
import type { AdminUser, AdminUserDetail } from '~/composables/useAdmin'

definePageMeta({
  layout: 'admin',
  middleware: ['auth', 'admin'],
})

const admin = useAdmin()

const users = ref<AdminUser[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')
const searchTimeout = ref<ReturnType<typeof setTimeout> | null>(null)

// User detail drawer
const selectedUser = ref<AdminUserDetail | null>(null)
const isLoadingDetail = ref(false)

async function loadUsers(email?: string) {
  isLoading.value = true
  error.value = null
  try {
    users.value = await admin.fetchUsers(email || undefined)
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load users'
  }
  finally {
    isLoading.value = false
  }
}

function handleSearch() {
  if (searchTimeout.value) clearTimeout(searchTimeout.value)
  searchTimeout.value = setTimeout(() => {
    loadUsers(searchQuery.value.trim() || undefined)
  }, 400)
}

async function viewUserDetail(userId: string) {
  isLoadingDetail.value = true
  try {
    selectedUser.value = await admin.fetchUser(userId)
  }
  catch {
    selectedUser.value = null
  }
  finally {
    isLoadingDetail.value = false
  }
}

function closeDetail() {
  selectedUser.value = null
}

async function toggleUserActive(user: AdminUser) {
  try {
    const updated = await admin.updateUser(user.id, { is_active: !user.is_active })
    const idx = users.value.findIndex(u => u.id === user.id)
    if (idx !== -1) users.value[idx] = { ...users.value[idx], is_active: updated.is_active }

    // Update detail view if same user
    if (selectedUser.value?.id === user.id) {
      selectedUser.value = { ...selectedUser.value, is_active: updated.is_active }
    }
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

watch(searchQuery, handleSearch)

onMounted(() => loadUsers())
</script>

<template>
  <div class="space-y-6 max-w-6xl mx-auto">
    <!-- Page Header -->
    <div>
      <h1 class="text-2xl font-bold text-horus-text-primary">Users</h1>
      <p class="text-sm text-horus-text-secondary mt-1">
        Search and manage platform users
      </p>
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
        placeholder="Search by email..."
        class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg pl-10 pr-4 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
      />
    </div>

    <!-- Error -->
    <HCard v-if="error" variant="elevated" padding="lg">
      <div class="flex items-center gap-3 text-horus-status-danger">
        <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 flex-shrink-0" />
        <div class="flex-1">
          <p class="font-medium">{{ error }}</p>
        </div>
        <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadUsers()">
          Retry
        </HButton>
      </div>
    </HCard>

    <!-- Loading -->
    <div v-else-if="isLoading" class="space-y-2">
      <HCard v-for="n in 6" :key="n" variant="elevated" padding="md">
        <div class="animate-pulse flex items-center gap-4">
          <div class="w-9 h-9 rounded-full bg-horus-bg-tertiary" />
          <div class="flex-1 space-y-2">
            <div class="h-4 w-40 rounded bg-horus-bg-tertiary" />
            <div class="h-3 w-56 rounded bg-horus-bg-tertiary" />
          </div>
        </div>
      </HCard>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Empty State -->
      <HCard v-if="users.length === 0" variant="elevated" padding="lg">
        <div class="py-8 text-center">
          <Icon name="heroicons:users" class="w-12 h-12 text-horus-text-muted mx-auto mb-3" />
          <p class="text-horus-text-secondary font-medium">
            {{ searchQuery ? 'No users match your search' : 'No users found' }}
          </p>
          <p v-if="searchQuery" class="text-sm text-horus-text-muted mt-1">
            Try a different email address
          </p>
        </div>
      </HCard>

      <!-- Users Table -->
      <div v-else class="flex gap-6">
        <div class="flex-1 min-w-0">
          <HCard variant="elevated" padding="none">
            <div class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-horus-border-subtle">
                    <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                      User
                    </th>
                    <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden md:table-cell">
                      Status
                    </th>
                    <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3 hidden lg:table-cell">
                      Joined
                    </th>
                    <th class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="user in users"
                    :key="user.id"
                    :class="[
                      'border-b border-horus-border-subtle last:border-0 transition-colors cursor-pointer',
                      selectedUser?.id === user.id
                        ? 'bg-horus-accent-cyan/5'
                        : 'hover:bg-horus-bg-tertiary/50',
                    ]"
                    @click="viewUserDetail(user.id)"
                  >
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-3 min-w-0">
                        <div class="w-8 h-8 rounded-full bg-horus-bg-tertiary flex items-center justify-center flex-shrink-0">
                          <Icon name="heroicons:user" class="w-4 h-4 text-horus-text-muted" />
                        </div>
                        <div class="min-w-0">
                          <p class="text-sm font-medium text-horus-text-primary truncate">
                            {{ user.display_name || 'No name' }}
                          </p>
                          <p class="text-xs text-horus-text-muted truncate">{{ user.email }}</p>
                        </div>
                      </div>
                    </td>
                    <td class="px-4 py-3 text-center hidden md:table-cell">
                      <HBadge :variant="user.is_active ? 'success' : 'idle'" size="sm">
                        {{ user.is_active ? 'Active' : 'Inactive' }}
                      </HBadge>
                    </td>
                    <td class="px-4 py-3 text-right hidden lg:table-cell">
                      <span class="text-xs text-horus-text-muted">{{ formatDate(user.created_at) }}</span>
                    </td>
                    <td class="px-4 py-3 text-right">
                      <button
                        class="p-1.5 rounded-md transition-colors"
                        :class="user.is_active
                          ? 'text-horus-text-muted hover:text-horus-status-warning hover:bg-horus-status-warning/10'
                          : 'text-horus-text-muted hover:text-horus-status-success hover:bg-horus-status-success/10'
                        "
                        :title="user.is_active ? 'Deactivate user' : 'Activate user'"
                        @click.stop="toggleUserActive(user)"
                      >
                        <Icon
                          :name="user.is_active ? 'heroicons:pause-circle' : 'heroicons:play-circle'"
                          class="w-4 h-4"
                        />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </HCard>
        </div>

        <!-- Detail Panel -->
        <Transition
          enter-active-class="transition-all duration-200"
          enter-from-class="opacity-0 translate-x-4"
          enter-to-class="opacity-100 translate-x-0"
          leave-active-class="transition-all duration-150"
          leave-from-class="opacity-100 translate-x-0"
          leave-to-class="opacity-0 translate-x-4"
        >
          <div v-if="selectedUser || isLoadingDetail" class="w-80 flex-shrink-0 hidden lg:block">
            <!-- Loading Detail -->
            <HCard v-if="isLoadingDetail" variant="elevated" padding="md">
              <div class="animate-pulse space-y-4">
                <div class="w-12 h-12 rounded-full bg-horus-bg-tertiary mx-auto" />
                <div class="h-4 w-32 rounded bg-horus-bg-tertiary mx-auto" />
                <div class="h-3 w-48 rounded bg-horus-bg-tertiary mx-auto" />
              </div>
            </HCard>

            <!-- User Detail -->
            <HCard v-else-if="selectedUser" variant="elevated" padding="md">
              <div class="space-y-5">
                <!-- Header -->
                <div class="flex items-start justify-between">
                  <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-horus-accent-cyan/10 flex items-center justify-center">
                      <Icon name="heroicons:user" class="w-5 h-5 text-horus-accent-cyan" />
                    </div>
                    <div class="min-w-0">
                      <p class="text-sm font-semibold text-horus-text-primary truncate">
                        {{ selectedUser.display_name || 'No name' }}
                      </p>
                      <p class="text-xs text-horus-text-muted truncate">{{ selectedUser.email }}</p>
                    </div>
                  </div>
                  <button
                    class="p-1 rounded text-horus-text-muted hover:text-horus-text-primary"
                    @click="closeDetail"
                  >
                    <Icon name="heroicons:x-mark" class="w-4 h-4" />
                  </button>
                </div>

                <!-- Info -->
                <div class="space-y-3 text-sm">
                  <div class="flex items-center justify-between">
                    <span class="text-horus-text-muted">Status</span>
                    <HBadge :variant="selectedUser.is_active ? 'success' : 'idle'" size="sm">
                      {{ selectedUser.is_active ? 'Active' : 'Inactive' }}
                    </HBadge>
                  </div>
                  <div class="flex items-center justify-between">
                    <span class="text-horus-text-muted">Joined</span>
                    <span class="text-horus-text-primary">{{ formatDate(selectedUser.created_at) }}</span>
                  </div>
                  <div class="flex items-center justify-between">
                    <span class="text-horus-text-muted">User ID</span>
                    <span class="text-xs text-horus-text-muted font-mono truncate max-w-[140px]">{{ selectedUser.id }}</span>
                  </div>
                </div>

                <!-- Seats -->
                <div class="border-t border-horus-border-subtle pt-4">
                  <p class="text-xs font-semibold text-horus-text-secondary uppercase tracking-wider mb-3">
                    Organization Seats
                  </p>
                  <div v-if="selectedUser.seats.length === 0" class="text-center py-3">
                    <p class="text-xs text-horus-text-muted">No org memberships</p>
                  </div>
                  <div v-else class="space-y-2">
                    <div
                      v-for="seat in selectedUser.seats"
                      :key="seat.id"
                      class="flex items-center justify-between p-2 rounded-lg bg-horus-bg-secondary"
                    >
                      <div class="min-w-0">
                        <p class="text-xs font-medium text-horus-text-primary truncate">
                          {{ seat.organization_id }}
                        </p>
                        <HBadge :variant="seat.is_active ? 'cyan' : 'idle'" size="sm" class="mt-1">
                          {{ seat.role }}
                        </HBadge>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Actions -->
                <div class="border-t border-horus-border-subtle pt-4">
                  <HButton
                    :variant="selectedUser.is_active ? 'danger' : 'success'"
                    size="sm"
                    class="w-full"
                    :icon="selectedUser.is_active ? 'heroicons:pause-circle' : 'heroicons:play-circle'"
                    @click="toggleUserActive(selectedUser)"
                  >
                    {{ selectedUser.is_active ? 'Deactivate User' : 'Activate User' }}
                  </HButton>
                </div>
              </div>
            </HCard>
          </div>
        </Transition>
      </div>
    </template>
  </div>
</template>
