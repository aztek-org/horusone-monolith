<script setup lang="ts">
const slots = defineSlots<{
  header?: () => unknown
  sidebar?: () => unknown
  default?: () => unknown
  panel?: () => unknown
  footer?: () => unknown
}>()

const isSidebarOpen = ref(true)
const isPanelOpen = ref(true)

// Nav sidebar (AppSidebar) state
const isNavOpen = ref(true)
const isMobile = ref(false)

function toggleNav() {
  isNavOpen.value = !isNavOpen.value
}

// Provide navState so AppHeader and AppSidebar can access it
provide('navState', { isNavOpen, toggleNav })

// Mobile responsive toggles
onMounted(() => {
  const checkMobile = () => {
    isMobile.value = window.innerWidth < 1024
    if (isMobile.value) {
      isSidebarOpen.value = false
      isPanelOpen.value = false
      isNavOpen.value = false
    } else {
      isSidebarOpen.value = true
      isPanelOpen.value = true
      isNavOpen.value = true
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

function closeNavOverlay() {
  if (isMobile.value) {
    isNavOpen.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen">
    <!-- App Navigation Sidebar (fixed left) -->
    <!-- Desktop: always visible when isNavOpen -->
    <div
      :class="[
        'hidden lg:block flex-shrink-0 sticky top-0 h-screen z-40 transition-all duration-300',
        isNavOpen ? 'w-60' : 'w-0 overflow-hidden',
      ]"
    >
      <AppSidebar v-if="isNavOpen" />
    </div>

    <!-- Mobile: overlay sidebar -->
    <Transition
      enter-active-class="transition-transform duration-300 ease-out"
      enter-from-class="-translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transition-transform duration-200 ease-in"
      leave-from-class="translate-x-0"
      leave-to-class="-translate-x-full"
    >
      <div
        v-if="isMobile && isNavOpen"
        class="fixed inset-y-0 left-0 z-50 w-60 shadow-2xl lg:hidden"
      >
        <AppSidebar />
      </div>
    </Transition>

    <!-- Content area (fills remaining width) -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Header -->
      <slot name="header">
        <AppHeader />
      </slot>
      
      <!-- Main Content Area -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Left Page Sidebar (slot-based, for page-specific content) -->
        <aside
          :class="[
            'flex-shrink-0 border-r border-horus-border-subtle bg-horus-bg-secondary/50 transition-all duration-300 overflow-y-auto',
            isSidebarOpen ? 'w-64 lg:w-72' : 'w-0',
            isMobile && isSidebarOpen && 'absolute inset-y-14 left-0 z-40 w-72 shadow-xl'
          ]"
        >
          <div v-if="isSidebarOpen" class="p-4">
            <slot name="sidebar" />
          </div>
        </aside>
        
        <!-- Mobile Sidebar Toggle -->
        <button
          v-if="isMobile"
          class="fixed left-2 top-16 z-30 p-2 rounded-lg bg-horus-bg-tertiary border border-horus-border-subtle shadow-lg lg:hidden"
          @click="toggleSidebar"
        >
          <Icon 
            :name="isSidebarOpen ? 'heroicons:chevron-left' : 'heroicons:bars-3-bottom-left'" 
            class="w-5 h-5 text-horus-text-secondary" 
          />
        </button>
        
        <!-- Main Content -->
        <main class="flex-1 overflow-y-auto">
          <slot />
        </main>
        
        <!-- Right Panel -->
        <aside
          :class="[
            'flex-shrink-0 border-l border-horus-border-subtle bg-horus-bg-secondary/50 transition-all duration-300 overflow-y-auto',
            isPanelOpen ? 'w-72 lg:w-80' : 'w-0',
            isMobile && isPanelOpen && 'absolute inset-y-14 right-0 z-40 w-80 shadow-xl'
          ]"
        >
          <div v-if="isPanelOpen" class="p-4">
            <slot name="panel" />
          </div>
        </aside>
        
        <!-- Mobile Panel Toggle -->
        <button
          v-if="isMobile"
          class="fixed right-2 top-16 z-30 p-2 rounded-lg bg-horus-bg-tertiary border border-horus-border-subtle shadow-lg lg:hidden"
          @click="togglePanel"
        >
          <Icon 
            :name="isPanelOpen ? 'heroicons:chevron-right' : 'heroicons:adjustments-horizontal'" 
            class="w-5 h-5 text-horus-text-secondary" 
          />
        </button>
      </div>
      
      <!-- Footer -->
      <slot name="footer">
        <AppFooter />
      </slot>
    </div>
    
    <!-- Mobile Nav Overlay (darkened backdrop) -->
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isMobile && isNavOpen"
        class="fixed inset-0 z-40 bg-black/50 lg:hidden"
        @click="closeNavOverlay"
      />
    </Transition>

    <!-- Mobile Page Sidebar/Panel Overlay -->
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

    <!-- Voice Communication Bubble -->
    <VoiceCommBubble />
  </div>
</template>
