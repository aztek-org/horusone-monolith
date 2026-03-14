<script setup lang="ts">
/**
 * Login page — shown when user is not authenticated.
 * Provides a button to redirect to Keycloak login.
 */
definePageMeta({
  layout: false,
})

const { login, isAuthenticated } = useAuth()
const router = useRouter()
const route = useRoute()

// If already authenticated, redirect away
watchEffect(() => {
  if (isAuthenticated.value) {
    const redirect = (route.query.redirect as string) || '/configurator'
    router.replace(redirect)
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-horus-bg-primary">
    <div class="w-full max-w-md rounded-xl border border-white/10 bg-horus-bg-secondary p-8 text-center">
      <h1 class="mb-2 text-2xl font-bold text-horus-text-primary">
        Horus
      </h1>
      <p class="mb-8 text-sm text-horus-text-secondary">
        AI-Powered Aviation Training Platform
      </p>

      <button
        class="w-full rounded-lg bg-horus-accent-cyan px-6 py-3 font-medium text-black transition-colors hover:bg-horus-accent-cyan/90"
        @click="login(($route.query.redirect as string) || undefined)"
      >
        Sign in with Keycloak
      </button>

      <p class="mt-6 text-xs text-horus-text-tertiary">
        By signing in, you agree to the Horus terms of service.
      </p>
    </div>
  </div>
</template>
