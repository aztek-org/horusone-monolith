<script setup lang="ts">
interface Props {
  title?: string
  subtitle?: string
  showSystemInfo?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Route & Scenario Architect',
  subtitle: 'TRAINING SYSTEM - HORUS v.0.2-tokyo',
  showSystemInfo: true
})

const route = useRoute()
const { state: simulation } = useSimulationState()
const { params: aiParams } = useAICopilot()
const { user, isAuthenticated, hasAnyRole, logout } = useAuth()

const navItems = computed(() => {
  const items = [
    { path: '/configurator', label: 'Configurator', icon: 'heroicons:cog-6-tooth' },
    { path: '/library', label: 'Library', icon: 'heroicons:book-open' },
    { path: '/flight-plan', label: 'Flight Plan', icon: 'heroicons:map' },
    { path: '/knowledge', label: 'Knowledge', icon: 'heroicons:academic-cap' },
    { path: '/assessments', label: 'Assessments', icon: 'heroicons:clipboard-document-check' },
    { path: '/stats', label: 'Stats', icon: 'heroicons:chart-bar-square' },
    { path: '/performance', label: 'Performance', icon: 'heroicons:chart-bar' },
    { path: '/leaderboard', label: 'Leaderboard', icon: 'heroicons:trophy' },
    { path: '/badges', label: 'Badges', icon: 'heroicons:star' },
  ]

  // Add Dashboard link for org-admin/instructor roles
  if (isAuthenticated.value && hasAnyRole('org-admin', 'instructor')) {
    items.unshift({ path: '/dashboard', label: 'Dashboard', icon: 'heroicons:squares-2x2' })
  }

  // Add Instructor link for instructor/org-admin roles
  if (isAuthenticated.value && hasAnyRole('instructor', 'org-admin')) {
    items.push({ path: '/instructor', label: 'Instructor', icon: 'heroicons:user-circle' })
  }

  // Add Admin link for platform-admin/org-admin roles
  if (isAuthenticated.value && hasAnyRole('platform-admin', 'org-admin')) {
    items.push({ path: '/admin', label: 'Admin', icon: 'heroicons:shield-check' })
  }

  return items
})

const isMobileMenuOpen = ref(false)
const isUserMenuOpen = ref(false)
const showAboutModal = ref(false)

const currentNav = computed(() =>
  navItems.value.find(item => route.path.startsWith(item.path))
)

const aiStatusLabel = computed(() =>
  aiParams.value.isOnline ? 'AI CO-PROCESSOR READY' : 'AI OFFLINE'
)

const userDisplayName = computed(() =>
  user.value?.displayName ?? 'Pilot'
)

const userEmail = computed(() =>
  user.value?.email ?? ''
)

const userAvatarSeed = computed(() =>
  user.value?.keycloakId ?? 'pilot'
)

function toggleMobileMenu() {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

function toggleUserMenu() {
  isUserMenuOpen.value = !isUserMenuOpen.value
}

function openAbout() {
  showAboutModal.value = true
  isUserMenuOpen.value = false
}

async function handleLogout() {
  isUserMenuOpen.value = false
  await logout()
}

// Close user menu when clicking outside
onMounted(() => {
  document.addEventListener('click', (e) => {
    const target = e.target as HTMLElement
    if (!target.closest('.user-menu-container')) {
      isUserMenuOpen.value = false
    }
  })
})
</script>

<template>
  <header class="sticky top-0 z-50 bg-horus-bg-primary/95 backdrop-blur-md border-b border-horus-border-subtle">
    <div class="flex items-center justify-between h-14 px-4 m-2 lg:px-6">
      <!-- Logo & Title -->
      <div class="flex items-center gap-4">
        <!-- Mobile Menu Toggle -->
        <button
          class="lg:hidden p-2 -ml-2 text-horus-text-secondary hover:text-horus-text-primary"
          @click="toggleMobileMenu"
        >
          <Icon :name="isMobileMenuOpen ? 'heroicons:x-mark' : 'heroicons:bars-3'" class="w-6 h-6" />
        </button>

        <!-- Logo -->
        <NuxtLink to="/" class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
            <Icon name="heroicons:paper-airplane" class="w-5 h-5 text-horus-accent-cyan" />
          </div>
          <div class="hidden sm:block">
            <h1 class="text-sm font-semibold text-horus-text-primary">{{ title }}</h1>
            <p class="text-xxs text-horus-text-muted tracking-wider">{{ subtitle }}</p>
          </div>
        </NuxtLink>
      </div>

      <!-- Desktop Navigation (client-only to prevent SSR hydration mismatch) -->
      <ClientOnly>
        <nav v-if="isAuthenticated" class="hidden lg:flex items-center gap-1">
          <NuxtLink
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            :class="[
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
              route.path.startsWith(item.path)
                ? 'bg-horus-bg-tertiary text-horus-text-primary'
                : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-secondary'
            ]"
          >
            <Icon :name="item.icon" class="w-4 h-4" />
            {{ item.label }}
          </NuxtLink>
        </nav>
      </ClientOnly>

      <!-- Right Section -->
      <div class="flex items-center gap-3">
        <!-- AI Status -->
        <HStatusPill
          :online="aiParams.isOnline"
          :label="aiStatusLabel"
          class="hidden sm:flex"
        />

        <!-- Primary Action -->
        <slot name="action">
          <HButton
            variant="primary"
            size="sm"
            icon="heroicons:play-solid"
            class="hidden sm:inline-flex"
          >
            EXECUTE SIMULATION
          </HButton>
        </slot>

        <!-- User Avatar / Login (client-only to prevent SSR hydration mismatch) -->
        <ClientOnly>
          <div v-if="isAuthenticated" class="relative user-menu-container">
            <button
              @click="toggleUserMenu"
              class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden hover:border-horus-accent-cyan transition-colors"
              :class="{ 'ring-2 ring-horus-accent-cyan': isUserMenuOpen }"
            >
              <img
                :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${userAvatarSeed}`"
                :alt="userDisplayName"
                class="w-full h-full object-cover"
              />
            </button>

            <!-- Dropdown Menu -->
            <Transition
              enter-active-class="transition-all duration-200 ease-out"
              enter-from-class="opacity-0 scale-95 -translate-y-2"
              enter-to-class="opacity-100 scale-100 translate-y-0"
              leave-active-class="transition-all duration-150 ease-in"
              leave-from-class="opacity-100 scale-100 translate-y-0"
              leave-to-class="opacity-0 scale-95 -translate-y-2"
            >
              <div
                v-if="isUserMenuOpen"
                class="absolute right-0 top-full mt-2 w-56 bg-horus-bg-elevated border border-horus-border-accent rounded-lg shadow-2xl overflow-hidden z-50"
              >
                <!-- User Info -->
                <div class="px-4 py-3 border-b border-horus-border-subtle">
                  <p class="text-sm font-medium text-horus-text-primary">{{ userDisplayName }}</p>
                  <p class="text-xs text-horus-text-muted">{{ userEmail }}</p>
                </div>

                <!-- Menu Items -->
                <div class="py-1">
                  <!-- Dashboard (org-admin/instructor only) -->
                  <NuxtLink
                    v-if="hasAnyRole('org-admin', 'instructor')"
                    to="/dashboard"
                    @click="isUserMenuOpen = false"
                    class="flex items-center gap-3 px-4 py-2.5 text-sm text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                  >
                    <Icon name="heroicons:squares-2x2" class="w-5 h-5 text-horus-text-secondary" />
                    <span>Dashboard</span>
                  </NuxtLink>

                  <!-- Admin Panel (platform-admin/org-admin only) -->
                  <NuxtLink
                    v-if="hasAnyRole('platform-admin', 'org-admin')"
                    to="/admin"
                    @click="isUserMenuOpen = false"
                    class="flex items-center gap-3 px-4 py-2.5 text-sm text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                  >
                    <Icon name="heroicons:shield-check" class="w-5 h-5 text-horus-text-secondary" />
                    <span>Admin Panel</span>
                  </NuxtLink>

                  <NuxtLink
                    to="/settings"
                    @click="isUserMenuOpen = false"
                    class="flex items-center gap-3 px-4 py-2.5 text-sm text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                  >
                    <Icon name="heroicons:cog-6-tooth" class="w-5 h-5 text-horus-text-secondary" />
                    <span>Settings</span>
                  </NuxtLink>

                  <button
                    @click="openAbout"
                    class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                  >
                    <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-text-secondary" />
                    <span>About Us</span>
                  </button>
                </div>

                <!-- Logout -->
                <div class="border-t border-horus-border-subtle py-1">
                  <button
                    @click="handleLogout"
                    class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-horus-status-danger hover:bg-horus-status-danger/10 transition-colors"
                  >
                    <Icon name="heroicons:arrow-right-on-rectangle" class="w-5 h-5" />
                    <span>Logout</span>
                  </button>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Login Button (Unauthenticated) -->
          <HButton
            v-else
            variant="primary"
            size="sm"
            icon="heroicons:arrow-right-on-rectangle"
            @click="() => { const { login } = useAuth(); login(route.fullPath) }"
          >
            Login
          </HButton>
        </ClientOnly>
      </div>
    </div>

    <!-- Mobile Navigation Drawer -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div v-if="isMobileMenuOpen" class="lg:hidden border-t border-horus-border-subtle bg-horus-bg-secondary/95 backdrop-blur-md">
        <nav v-if="isAuthenticated" class="p-2 space-y-1">
          <NuxtLink
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            :class="[
              'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors',
              route.path.startsWith(item.path)
                ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan'
                : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary'
            ]"
            @click="isMobileMenuOpen = false"
          >
            <Icon :name="item.icon" class="w-5 h-5" />
            {{ item.label }}
          </NuxtLink>
        </nav>

        <!-- Mobile AI Status & Action -->
        <div class="p-4 pt-2 space-y-3 border-t border-horus-border-subtle">
          <HStatusPill
            :online="aiParams.isOnline"
            :label="aiStatusLabel"
            class="w-full justify-center"
          />
          <HButton
            variant="primary"
            size="md"
            icon="heroicons:play-solid"
            class="w-full"
          >
            EXECUTE SIMULATION
          </HButton>
        </div>
      </div>
    </Transition>

    <!-- About Modal -->
    <AboutModal v-model="showAboutModal" />
  </header>
</template>
