<script setup lang="ts">
interface Props {
  title?: string
  subtitle?: string
  showSystemInfo?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Route & Scenario Architect',
  subtitle: 'TRAINING SYSTEM V4.0',
  showSystemInfo: true
})

const route = useRoute()
const { state: simulation } = useSimulationState()
const { params: aiParams } = useAICopilot()

const navItems = [
  { path: '/configurator', label: 'Configurator', icon: 'heroicons:cog-6-tooth' },
  { path: '/library', label: 'Library', icon: 'heroicons:book-open' },
  { path: '/performance', label: 'Performance', icon: 'heroicons:chart-bar' }
]

const isMobileMenuOpen = ref(false)

const currentNav = computed(() => 
  navItems.find(item => route.path.startsWith(item.path))
)

const aiStatusLabel = computed(() => 
  aiParams.value.isOnline ? 'AI CO-PROCESSOR READY' : 'AI OFFLINE'
)

function toggleMobileMenu() {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}
</script>

<template>
  <header class="sticky top-0 z-50 bg-horus-bg-primary/95 backdrop-blur-md border-b border-horus-border-subtle">
    <div class="flex items-center justify-between h-14 px-4 lg:px-6">
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
      
      <!-- Desktop Navigation -->
      <nav class="hidden lg:flex items-center gap-1">
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
        
        <!-- User Avatar -->
        <button class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden">
          <img 
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=pilot" 
            alt="User" 
            class="w-full h-full object-cover"
          />
        </button>
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
        <nav class="p-2 space-y-1">
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
  </header>
</template>
