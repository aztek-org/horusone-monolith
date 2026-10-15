<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
/**
 * Admin layout: simplified header (no main nav) + sidebar + content area.
 * The main app nav (Configurator, Library, etc.) is hidden in admin context
 * to avoid a double-navbar appearance.
 */
const { user, isAuthenticated, logout } = useAuth()

const isUserMenuOpen = ref(false)

const userDisplayName = computed(() => user.value?.displayName ?? 'Admin')
const userEmail = computed(() => user.value?.email ?? '')
const userAvatarSeed = computed(() => user.value?.keycloakId ?? 'admin')

function toggleUserMenu() {
  isUserMenuOpen.value = !isUserMenuOpen.value
}

async function handleLogout() {
  isUserMenuOpen.value = false
  await logout()
}

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
  <div class="flex flex-col min-h-screen bg-horus-bg-primary">
    <!-- Simplified Admin Header -->
    <header class="sticky top-0 z-50 bg-horus-bg-primary/95 backdrop-blur-md border-b border-horus-border-subtle">
      <div class="flex items-center justify-between h-14 px-4 lg:px-6">
        <!-- Logo & Title -->
        <div class="flex items-center gap-4">
          <NuxtLink
            to="/admin"
            class="flex items-center gap-3"
          >
            <div class="w-8 h-8 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
              <Icon
                name="heroicons:shield-check"
                class="w-5 h-5 text-horus-accent-cyan"
              />
            </div>
            <div>
              <h1 class="text-sm font-semibold text-horus-text-primary">Horus Admin</h1>
              <p class="text-xxs text-horus-text-muted tracking-wider">PLATFORM MANAGEMENT</p>
            </div>
          </NuxtLink>
        </div>

        <!-- Right: Back to App + User Menu -->
        <div class="flex items-center gap-3">
          <NuxtLink
            to="/configurator"
            class="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-secondary transition-colors"
          >
            <Icon
              name="heroicons:arrow-left"
              class="w-4 h-4"
            />
            <span class="hidden sm:inline">Back to App</span>
          </NuxtLink>

          <!-- User Menu -->
          <div
            v-if="isAuthenticated"
            class="relative user-menu-container"
          >
            <button
              class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden hover:border-horus-accent-cyan transition-colors"
              :class="{ 'ring-2 ring-horus-accent-cyan': isUserMenuOpen }"
              @click="toggleUserMenu"
            >
              <img
                :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${userAvatarSeed}`"
                :alt="userDisplayName"
                class="w-full h-full object-cover"
              >
            </button>

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
                <div class="px-4 py-3 border-b border-horus-border-subtle">
                  <p class="text-sm font-medium text-horus-text-primary">
                    {{ userDisplayName }}
                  </p>
                  <p class="text-xs text-horus-text-muted">
                    {{ userEmail }}
                  </p>
                </div>
                <div class="py-1">
                  <NuxtLink
                    to="/settings"
                    class="flex items-center gap-3 px-4 py-2.5 text-sm text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                    @click="isUserMenuOpen = false"
                  >
                    <Icon
                      name="heroicons:cog-6-tooth"
                      class="w-5 h-5 text-horus-text-secondary"
                    />
                    <span>Settings</span>
                  </NuxtLink>
                </div>
                <div class="border-t border-horus-border-subtle py-1">
                  <button
                    class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-horus-status-danger hover:bg-horus-status-danger/10 transition-colors"
                    @click="handleLogout"
                  >
                    <Icon
                      name="heroicons:arrow-right-on-rectangle"
                      class="w-5 h-5"
                    />
                    <span>Logout</span>
                  </button>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </header>

    <div class="flex-1 flex overflow-hidden">
      <AdminSidebar class="hidden lg:flex lg:flex-col" />

      <main class="flex-1 overflow-y-auto p-4 lg:p-6">
        <slot />
      </main>
    </div>
  </div>
</template>
