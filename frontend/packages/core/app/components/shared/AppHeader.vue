<script setup lang="ts">
const route = useRoute()
const { params: aiParams } = useAICopilot()

const aiStatusLabel = computed(() =>
  aiParams.value.isOnline ? 'AI CO-PROCESSOR READY' : 'AI OFFLINE',
)

// Page title derived from current route
const pageTitle = computed(() => {
  const pathToTitle: Record<string, string> = {
    '/': 'Home',
    '/configurator': 'Configurator',
    '/library': 'Library',
    '/flight-plan': 'Flight Plan',
    '/knowledge': 'Knowledge',
    '/assessments': 'Assessments',
    '/stats': 'Stats',
    '/performance': 'Performance',
    '/leaderboard': 'Leaderboard',
    '/badges': 'Badges',
    '/dashboard': 'Dashboard',
    '/instructor': 'Instructor',
    '/admin': 'Admin',
    '/settings': 'Settings',
  }

  // Check exact match first, then prefix match
  if (pathToTitle[route.path]) return pathToTitle[route.path]

  for (const [path, title] of Object.entries(pathToTitle)) {
    if (path !== '/' && route.path.startsWith(path)) return title
  }

  // Fallback: derive from route name or path
  const name = route.name?.toString() ?? ''
  if (name) {
    return name
      .replace(/-/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase())
  }

  return 'Horus'
})

// Inject navState from the default layout for mobile sidebar toggle
const navState = inject<{ isNavOpen: Ref<boolean>, toggleNav: () => void }>('navState')
const isDesktop = ref(false)
const isDesktopNavExpanded = computed(() => !!navState?.isNavOpen.value && isDesktop.value)

function handleResize() {
  if (import.meta.client) {
    isDesktop.value = window.innerWidth >= 1024
  }
}

function handleToggleNav() {
  navState?.toggleNav()
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (import.meta.client) {
    window.removeEventListener('resize', handleResize)
  }
})
</script>

<template>
  <header class="sticky top-0 z-50 bg-horus-bg-primary/95 backdrop-blur-md border-b border-horus-border-subtle">
    <div class="flex items-center justify-between h-14 px-4 lg:px-6">
      <!-- Left: Hamburger toggle (mobile) + Page Title -->
      <div class="flex items-center gap-3">
        <!-- Desktop Sidebar Toggle -->
        <button
          class="hidden lg:inline-flex p-2 -ml-2 text-horus-text-secondary hover:text-horus-text-primary transition-colors"
          :title="isDesktopNavExpanded ? 'Collapse navigation' : 'Expand navigation'"
          @click="handleToggleNav"
        >
          <Icon
            :name="isDesktopNavExpanded ? 'heroicons:chevron-double-left' : 'heroicons:chevron-double-right'"
            class="w-5 h-5"
          />
        </button>

        <!-- Mobile Sidebar Toggle -->
        <button
          class="lg:hidden p-2 -ml-2 text-horus-text-secondary hover:text-horus-text-primary transition-colors"
          @click="handleToggleNav"
        >
          <Icon
            :name="navState?.isNavOpen.value ? 'heroicons:x-mark' : 'heroicons:bars-3'"
            class="w-6 h-6"
          />
        </button>

        <!-- Page Title / Breadcrumb -->
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-semibold text-horus-text-primary">
            {{ pageTitle }}
          </h1>
          <span class="text-xxs text-horus-text-muted tracking-wider uppercase hidden sm:inline">
            HORUS v0.2
          </span>
        </div>
      </div>

      <!-- Right: AI Status + Execute Simulation -->
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
      </div>
    </div>
  </header>
</template>
