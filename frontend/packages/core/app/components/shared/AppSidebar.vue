<script setup lang="ts">
const route = useRoute()
const { user, isAuthenticated, hasAnyRole, login, logout } = useAuth()
const showAboutModal = ref(false)

const props = withDefaults(
  defineProps<{
    collapsed?: boolean
  }>(),
  {
    collapsed: false,
  },
)

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

const isCollapsed = computed(() => props.collapsed)
const userDisplayName = computed(() => user.value?.displayName ?? 'Pilot')
const userEmail = computed(() => user.value?.email ?? '')
const userAvatarSeed = computed(() => user.value?.keycloakId ?? 'pilot')

function handleLogin() {
  login(route.fullPath)
}

async function handleLogout() {
  await logout()
}

function openAbout() {
  showAboutModal.value = true
}

// Inject navState from the default layout
const navState = inject<{ isNavOpen: Ref<boolean>, toggleNav: () => void }>('navState')

function closeMobileNav() {
  if (navState && import.meta.client && window.innerWidth < 1024) {
    navState.isNavOpen.value = false
  }
}
</script>

<template>
  <aside
    :class="[
      'h-screen flex-shrink-0 bg-horus-bg-secondary/50 border-r border-horus-border-subtle flex flex-col overflow-hidden transition-all duration-300',
      isCollapsed ? 'w-16' : 'w-60',
    ]"
  >
    <!-- Logo & Title -->
    <div :class="['flex-shrink-0 border-b border-horus-border-subtle', isCollapsed ? 'px-2 pt-4 pb-3' : 'px-4 pt-5 pb-4']">
      <NuxtLink
        to="/"
        :class="[
          'flex items-center',
          isCollapsed ? 'justify-center' : 'gap-3',
        ]"
        @click="closeMobileNav"
      >
        <div
          :class="[
            'rounded-lg border border-horus-border-subtle bg-horus-bg-tertiary/80 flex items-center justify-center flex-shrink-0',
            isCollapsed ? 'w-10 h-10 p-1.5' : 'w-8 h-8 p-1',
          ]"
        >
          <img
            src="/logo.svg"
            alt="Horus logo"
            class="w-full h-full object-contain"
          >
        </div>
        <div
          v-if="!isCollapsed"
          class="min-w-0"
        >
          <h1 class="text-sm font-semibold text-horus-text-primary truncate">Horus Aviation</h1>
          <p class="text-xxs text-horus-text-muted tracking-wider uppercase">Training Platform</p>
        </div>
      </NuxtLink>
    </div>

    <!-- Navigation Groups -->
    <nav :class="['flex-1 overflow-y-auto', isCollapsed ? 'px-2 py-3 space-y-2' : 'px-3 py-4 space-y-4']">
      <ClientOnly>
        <template v-if="isAuthenticated">
          <div
            v-for="(group, groupIndex) in navGroups"
            :key="group.key"
            :class="[
              isCollapsed && groupIndex > 0 ? 'mt-2 pt-2 border-t border-horus-border-subtle/70' : '',
            ]"
          >
            <!-- Section Header (clickable to expand/collapse) -->
            <button
              v-if="!isCollapsed"
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
              v-if="!isCollapsed"
              enter-active-class="transition-all duration-200 ease-out"
              enter-from-class="opacity-0 max-h-0"
              enter-to-class="opacity-100 max-h-96"
              leave-active-class="transition-all duration-150 ease-in"
              leave-from-class="opacity-100 max-h-96"
              leave-to-class="opacity-0 max-h-0"
            >
              <div
                v-show="expandedSections[group.key]"
                class="space-y-0.5 overflow-hidden"
              >
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

            <!-- Collapsed: icon rail -->
            <div
              v-else
              class="space-y-1"
            >
              <NuxtLink
                v-for="item in group.items"
                :key="item.path"
                :to="item.path"
                :title="item.label"
                :aria-label="item.label"
                :class="[
                  'flex items-center justify-center w-10 h-10 mx-auto rounded-lg transition-all duration-150 border',
                  isItemActive(item.path)
                    ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border-horus-accent-cyan/20'
                    : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary border-transparent',
                ]"
                @click="closeMobileNav"
              >
                <Icon
                  :name="item.icon"
                  :class="[
                    'w-5 h-5',
                    isItemActive(item.path) ? 'text-horus-accent-cyan' : 'text-horus-text-muted',
                  ]"
                />
              </NuxtLink>
            </div>
          </div>
        </template>

        <!-- Unauthenticated state -->
        <template v-else>
          <div :class="[isCollapsed ? 'px-0 py-2' : 'px-2 py-4 text-center']">
            <p
              v-if="!isCollapsed"
              class="text-sm text-horus-text-muted mb-3"
            >
              Sign in to access navigation
            </p>
            <HButton
              variant="primary"
              :size="isCollapsed ? 'md' : 'sm'"
              icon="heroicons:arrow-right-on-rectangle"
              :class="isCollapsed ? 'w-10 h-10 mx-auto !p-0 !min-w-0' : 'w-full'"
              :title="isCollapsed ? 'Login' : undefined"
              @click="handleLogin"
            >
              <span v-if="!isCollapsed">Login</span>
            </HButton>
          </div>
        </template>
      </ClientOnly>
    </nav>

    <!-- Bottom Section: About + User -->
    <div class="flex-shrink-0 border-t border-horus-border-subtle">
      <!-- About Link -->
      <button
        :class="[
          'w-full text-sm text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors',
          isCollapsed ? 'flex items-center justify-center px-2 py-2.5' : 'flex items-center gap-3 px-5 py-2.5',
        ]"
        :title="isCollapsed ? 'About' : undefined"
        @click="openAbout"
      >
        <Icon
          name="heroicons:information-circle"
          class="w-5 h-5 flex-shrink-0"
        />
        <span v-if="!isCollapsed">About</span>
      </button>

      <!-- Settings Link -->
      <ClientOnly>
        <NuxtLink
          v-if="isAuthenticated"
          to="/settings"
          :class="[
            'text-sm text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors',
            isCollapsed ? 'flex items-center justify-center px-2 py-2.5' : 'flex items-center gap-3 px-5 py-2.5',
          ]"
          :title="isCollapsed ? 'Settings' : undefined"
          @click="closeMobileNav"
        >
          <Icon
            name="heroicons:cog-6-tooth"
            class="w-5 h-5 flex-shrink-0"
          />
          <span v-if="!isCollapsed">Settings</span>
        </NuxtLink>
      </ClientOnly>

      <!-- User Info + Logout -->
      <ClientOnly>
        <div
          v-if="isAuthenticated"
          :class="[
            isCollapsed ? 'px-2 py-3 flex flex-col items-center gap-2' : 'px-4 py-3 flex items-center gap-3',
          ]"
        >
          <div class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden flex-shrink-0">
            <img
              :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${userAvatarSeed}`"
              :alt="userDisplayName"
              class="w-full h-full object-cover"
            >
          </div>
          <div
            v-if="!isCollapsed"
            class="min-w-0 flex-1"
          >
            <p class="text-sm font-medium text-horus-text-primary truncate">
              {{ userDisplayName }}
            </p>
            <p class="text-xxs text-horus-text-muted truncate">
              {{ userEmail }}
            </p>
          </div>
          <button
            class="p-1.5 rounded-lg text-horus-text-muted hover:text-horus-status-danger hover:bg-horus-status-danger/10 transition-colors flex-shrink-0"
            :title="isCollapsed ? `Logout ${userDisplayName}` : 'Logout'"
            @click="handleLogout"
          >
            <Icon
              name="heroicons:arrow-right-on-rectangle"
              class="w-4 h-4"
            />
          </button>
        </div>
      </ClientOnly>
    </div>

    <!-- About Modal -->
    <AboutModal v-model="showAboutModal" />
  </aside>
</template>
