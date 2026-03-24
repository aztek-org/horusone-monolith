<script setup lang="ts">
const route = useRoute()
const { user, isAuthenticated, hasAnyRole, logout } = useAuth()
const showAboutModal = ref(false)

interface NavItem {
  path: string
  label: string
  icon: string
}

interface NavGroup {
  key: string
  label: string
  icon: string
  items: NavItem[]
}

const navGroups = computed<NavGroup[]>(() => {
  const groups: NavGroup[] = [
    {
      key: 'training',
      label: 'Training',
      icon: 'heroicons:rocket-launch',
      items: [
        { path: '/configurator', label: 'Configurator', icon: 'heroicons:cog-6-tooth' },
        { path: '/library', label: 'Library', icon: 'heroicons:book-open' },
        { path: '/flight-plan', label: 'Flight Plan', icon: 'heroicons:map' },
      ],
    },
    {
      key: 'learning',
      label: 'Learning',
      icon: 'heroicons:academic-cap',
      items: [
        { path: '/knowledge', label: 'Knowledge', icon: 'heroicons:academic-cap' },
        { path: '/assessments', label: 'Assessments', icon: 'heroicons:clipboard-document-check' },
      ],
    },
    {
      key: 'progress',
      label: 'Progress',
      icon: 'heroicons:chart-bar-square',
      items: [
        { path: '/stats', label: 'Stats', icon: 'heroicons:chart-bar-square' },
        { path: '/performance', label: 'Performance', icon: 'heroicons:chart-bar' },
        { path: '/leaderboard', label: 'Leaderboard', icon: 'heroicons:trophy' },
        { path: '/badges', label: 'Badges', icon: 'heroicons:star' },
      ],
    },
  ]

  // Management group (role-gated)
  const managementItems: NavItem[] = []
  if (hasAnyRole('org-admin', 'instructor')) {
    managementItems.push({ path: '/dashboard', label: 'Dashboard', icon: 'heroicons:squares-2x2' })
  }
  if (hasAnyRole('instructor', 'org-admin')) {
    managementItems.push({ path: '/instructor', label: 'Instructor', icon: 'heroicons:user-circle' })
  }
  if (hasAnyRole('platform-admin', 'org-admin')) {
    managementItems.push({ path: '/admin', label: 'Admin', icon: 'heroicons:shield-check' })
  }
  if (managementItems.length > 0) {
    groups.push({
      key: 'management',
      label: 'Management',
      icon: 'heroicons:cog-6-tooth',
      items: managementItems,
    })
  }

  return groups
})

// Section expand/collapse state — all expanded by default
const expandedSections = ref<Record<string, boolean>>({
  training: true,
  learning: true,
  progress: true,
  management: true,
})

function toggleSection(key: string) {
  expandedSections.value[key] = !expandedSections.value[key]
}

function isItemActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}

const userDisplayName = computed(() => user.value?.displayName ?? 'Pilot')
const userEmail = computed(() => user.value?.email ?? '')
const userAvatarSeed = computed(() => user.value?.keycloakId ?? 'pilot')

async function handleLogout() {
  await logout()
}

function openAbout() {
  showAboutModal.value = true
}

// Inject navState from the default layout
const navState = inject<{ isNavOpen: Ref<boolean>; toggleNav: () => void }>('navState')

function closeMobileNav() {
  if (navState && window.innerWidth < 1024) {
    navState.isNavOpen.value = false
  }
}
</script>

<template>
  <aside
    class="h-screen w-60 flex-shrink-0 bg-horus-bg-secondary/50 border-r border-horus-border-subtle flex flex-col overflow-hidden"
  >
    <!-- Logo & Title -->
    <div class="flex-shrink-0 px-4 pt-5 pb-4 border-b border-horus-border-subtle">
      <NuxtLink to="/" class="flex items-center gap-3" @click="closeMobileNav">
        <div class="w-8 h-8 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center flex-shrink-0">
          <Icon name="heroicons:paper-airplane" class="w-5 h-5 text-horus-accent-cyan" />
        </div>
        <div class="min-w-0">
          <h1 class="text-sm font-semibold text-horus-text-primary truncate">Horus Aviation</h1>
          <p class="text-xxs text-horus-text-muted tracking-wider uppercase">Training Platform</p>
        </div>
      </NuxtLink>
    </div>

    <!-- Navigation Groups -->
    <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-4">
      <ClientOnly>
        <template v-if="isAuthenticated">
          <div v-for="group in navGroups" :key="group.key">
            <!-- Section Header (clickable to expand/collapse) -->
            <button
              class="w-full flex items-center justify-between px-2 py-1.5 mb-1 group"
              @click="toggleSection(group.key)"
            >
              <span class="text-xxs text-horus-text-muted uppercase tracking-wider font-semibold">
                {{ group.label }}
              </span>
              <Icon
                name="heroicons:chevron-down"
                :class="[
                  'w-3.5 h-3.5 text-horus-text-muted transition-transform duration-200',
                  expandedSections[group.key] ? 'rotate-0' : '-rotate-90',
                ]"
              />
            </button>

            <!-- Section Items with transition -->
            <Transition
              enter-active-class="transition-all duration-200 ease-out"
              enter-from-class="opacity-0 max-h-0"
              enter-to-class="opacity-100 max-h-96"
              leave-active-class="transition-all duration-150 ease-in"
              leave-from-class="opacity-100 max-h-96"
              leave-to-class="opacity-0 max-h-0"
            >
              <div v-show="expandedSections[group.key]" class="space-y-0.5 overflow-hidden">
                <NuxtLink
                  v-for="item in group.items"
                  :key="item.path"
                  :to="item.path"
                  :class="[
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                    isItemActive(item.path)
                      ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border border-horus-accent-cyan/20'
                      : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary border border-transparent',
                  ]"
                  @click="closeMobileNav"
                >
                  <Icon
                    :name="item.icon"
                    :class="[
                      'w-5 h-5 flex-shrink-0',
                      isItemActive(item.path) ? 'text-horus-accent-cyan' : 'text-horus-text-muted',
                    ]"
                  />
                  <span class="truncate">{{ item.label }}</span>
                </NuxtLink>
              </div>
            </Transition>
          </div>
        </template>

        <!-- Unauthenticated state -->
        <template v-else>
          <div class="px-2 py-4 text-center">
            <p class="text-sm text-horus-text-muted mb-3">Sign in to access navigation</p>
            <HButton
              variant="primary"
              size="sm"
              icon="heroicons:arrow-right-on-rectangle"
              class="w-full"
              @click="() => { const { login } = useAuth(); login(route.fullPath) }"
            >
              Login
            </HButton>
          </div>
        </template>
      </ClientOnly>
    </nav>

    <!-- Bottom Section: About + User -->
    <div class="flex-shrink-0 border-t border-horus-border-subtle">
      <!-- About Link -->
      <button
        class="w-full flex items-center gap-3 px-5 py-2.5 text-sm text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
        @click="openAbout"
      >
        <Icon name="heroicons:information-circle" class="w-5 h-5 flex-shrink-0" />
        <span>About</span>
      </button>

      <!-- Settings Link -->
      <ClientOnly>
        <NuxtLink
          v-if="isAuthenticated"
          to="/settings"
          class="flex items-center gap-3 px-5 py-2.5 text-sm text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
          @click="closeMobileNav"
        >
          <Icon name="heroicons:cog-6-tooth" class="w-5 h-5 flex-shrink-0" />
          <span>Settings</span>
        </NuxtLink>
      </ClientOnly>

      <!-- User Info + Logout -->
      <ClientOnly>
        <div v-if="isAuthenticated" class="px-4 py-3 flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden flex-shrink-0">
            <img
              :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${userAvatarSeed}`"
              :alt="userDisplayName"
              class="w-full h-full object-cover"
            />
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-horus-text-primary truncate">{{ userDisplayName }}</p>
            <p class="text-xxs text-horus-text-muted truncate">{{ userEmail }}</p>
          </div>
          <button
            class="p-1.5 rounded-lg text-horus-text-muted hover:text-horus-status-danger hover:bg-horus-status-danger/10 transition-colors flex-shrink-0"
            title="Logout"
            @click="handleLogout"
          >
            <Icon name="heroicons:arrow-right-on-rectangle" class="w-4 h-4" />
          </button>
        </div>
      </ClientOnly>
    </div>

    <!-- About Modal -->
    <AboutModal v-model="showAboutModal" />
  </aside>
</template>
