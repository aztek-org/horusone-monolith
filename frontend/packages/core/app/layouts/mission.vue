<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
// Mission layout - similar to default but with mission-specific header
const route = useRoute()
const { state: simulation } = useSimulationState()
const { params: aiParams } = useAICopilot()

const isSidebarOpen = ref(true)
const isPanelOpen = ref(true)
const isMobile = ref(false)

const missionId = computed(() => route.params.id as string || 'X-RAY-042-ALPHA')

onMounted(() => {
  const checkMobile = () => {
    isMobile.value = window.innerWidth < 1024
    if (isMobile.value) {
      isSidebarOpen.value = false
      isPanelOpen.value = false
    }
    else {
      isSidebarOpen.value = true
      isPanelOpen.value = true
    }
  }

  checkMobile()
  window.addEventListener('resize', checkMobile)

  onUnmounted(() => {
    window.removeEventListener('resize', checkMobile)
  })
})

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
  if (isMobile.value && isSidebarOpen.value) {
    isPanelOpen.value = false
  }
}

function togglePanel() {
  isPanelOpen.value = !isPanelOpen.value
  if (isMobile.value && isPanelOpen.value) {
    isSidebarOpen.value = false
  }
}
</script>

<template>
  <div class="flex flex-col min-h-screen">
    <!-- Mission Header -->
    <header class="sticky top-0 z-50 bg-horus-bg-primary/95 backdrop-blur-md border-b border-horus-border-subtle">
      <div class="flex items-center justify-between h-14 px-4 lg:px-6">
        <!-- Logo & Mission Info -->
        <div class="flex items-center gap-4">
          <!-- Mobile Menu Toggle -->
          <button
            class="lg:hidden p-2 -ml-2 text-horus-text-secondary hover:text-horus-text-primary"
            @click="toggleSidebar"
          >
            <Icon
              name="heroicons:bars-3"
              class="w-6 h-6"
            />
          </button>

          <!-- Logo -->
          <NuxtLink
            to="/"
            class="flex items-center gap-3"
          >
            <div class="w-8 h-8 rounded-lg bg-horus-status-warning/20 flex items-center justify-center">
              <Icon
                name="heroicons:exclamation-triangle"
                class="w-5 h-5 text-horus-status-warning"
              />
            </div>
            <div class="hidden sm:block">
              <h1 class="text-sm font-semibold text-horus-text-primary">Mission Decision Hub</h1>
            </div>
          </NuxtLink>

          <!-- Mission ID -->
          <div class="hidden md:flex items-center gap-2 px-3 py-1 rounded bg-horus-bg-secondary border border-horus-border-subtle">
            <span class="text-xxs text-horus-text-muted">MISSION ID:</span>
            <span class="text-xs font-mono text-horus-text-primary">{{ missionId }}</span>
          </div>

          <!-- Current Phase -->
          <div class="hidden lg:flex items-center gap-2 px-3 py-1 rounded bg-horus-status-warning/10 border border-horus-status-warning/30">
            <span class="text-xxs text-horus-text-muted">CURRENT PHASE:</span>
            <span class="text-xs font-semibold text-horus-status-warning">{{ simulation.phase }}</span>
          </div>
        </div>

        <!-- Center Status -->
        <div class="hidden lg:flex items-center gap-3">
          <HStatusPill
            :online="aiParams.isOnline"
            label="AI COPILOT ONLINE"
            variant="success"
          />
        </div>

        <!-- Right Section -->
        <div class="flex items-center gap-3">
          <!-- Emergency Reset -->
          <HButton
            variant="danger"
            size="sm"
            icon="heroicons:arrow-path"
          >
            <span class="hidden sm:inline">EMERGENCY RESET</span>
          </HButton>

          <!-- Panel Toggle (Mobile) -->
          <button
            class="lg:hidden p-2 text-horus-text-secondary hover:text-horus-text-primary"
            @click="togglePanel"
          >
            <Icon
              name="heroicons:adjustments-horizontal"
              class="w-6 h-6"
            />
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content Area -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Left Sidebar -->
      <aside
        :class="[
          'flex-shrink-0 border-r border-horus-border-subtle bg-horus-bg-secondary/50 transition-all duration-300 overflow-y-auto',
          isSidebarOpen ? 'w-64 lg:w-72' : 'w-0',
          isMobile && isSidebarOpen && 'absolute inset-y-14 left-0 z-40 w-72 shadow-xl bg-horus-bg-primary',
        ]"
      >
        <div
          v-if="isSidebarOpen"
          class="p-4"
        >
          <slot name="sidebar" />
        </div>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 overflow-y-auto p-4 lg:p-6">
        <slot />
      </main>

      <!-- Right Panel -->
      <aside
        :class="[
          'flex-shrink-0 border-l border-horus-border-subtle bg-horus-bg-secondary/50 transition-all duration-300 overflow-y-auto',
          isPanelOpen ? 'w-72 lg:w-80' : 'w-0',
          isMobile && isPanelOpen && 'absolute inset-y-14 right-0 z-40 w-80 shadow-xl bg-horus-bg-primary',
        ]"
      >
        <div
          v-if="isPanelOpen"
          class="p-4"
        >
          <slot name="panel" />
        </div>
      </aside>
    </div>

    <!-- Footer -->
    <AppFooter />

    <!-- Mobile Overlay -->
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isMobile && (isSidebarOpen || isPanelOpen)"
        class="fixed inset-0 z-30 bg-black/50"
        @click="isSidebarOpen = false; isPanelOpen = false"
      />
    </Transition>
  </div>
</template>
