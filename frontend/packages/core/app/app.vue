<script setup lang="ts">
const { isAuthenticated, isLoading } = useAuth()
const route = useRoute()

const publicRoutes = ['/login', '/auth/callback']
const isPublicRoute = computed(() => publicRoutes.some(r => route.path.startsWith(r)))

/**
 * Show content only when:
 * - The route is public (login, callback), OR
 * - Auth has finished loading (no flash of protected content)
 */
const showContent = computed(() => isPublicRoute.value || !isLoading.value)
</script>

<template>
  <div>
    <NuxtRouteAnnouncer />
    <NuxtLayout v-if="showContent">
      <NuxtPage />
    </NuxtLayout>
    <!-- Global auth loading screen — prevents flash of protected pages -->
    <div v-if="!showContent" class="flex min-h-screen items-center justify-center bg-horus-bg-primary">
      <div class="text-center space-y-4">
        <Icon name="svg-spinners:ring-resize" class="w-12 h-12 text-horus-accent-cyan mx-auto" />
        <p class="text-horus-text-secondary text-sm">Authenticating…</p>
      </div>
    </div>
  </div>
</template>
