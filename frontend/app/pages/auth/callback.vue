<script setup lang="ts">
/**
 * OIDC callback page — handles Keycloak redirect after login.
 * Exchanges the authorization code for tokens, then redirects to the
 * originally requested page (or home).
 *
 * SSR is disabled (ssr: false) to ensure sessionStorage and URL params
 * are always available during hydration.
 */
definePageMeta({
  layout: false,
  ssr: false,
})

const { handleCallback, login, isAuthenticated, error } = useAuth()
const router = useRouter()

onMounted(async () => {
  await handleCallback()

  if (isAuthenticated.value) {
    const redirect = sessionStorage.getItem('auth_redirect') || '/configurator'
    sessionStorage.removeItem('auth_redirect')
    router.replace(redirect)
  }
})

function retryLogin(): void {
  const redirect = sessionStorage.getItem('auth_redirect')
  login(redirect || undefined)
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-horus-bg-primary">
    <div class="text-center">
      <div
        v-if="!error"
        class="text-horus-text-secondary"
      >
        <div class="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-horus-accent-cyan border-t-transparent" />
        <p>Authenticating...</p>
      </div>
      <div
        v-else
        class="text-red-400"
      >
        <p class="text-lg font-medium">
          Authentication Failed
        </p>
        <p class="mt-2 text-sm">
          {{ error }}
        </p>
        <div class="mt-4 flex justify-center gap-3">
          <button
            class="rounded bg-horus-accent-cyan px-4 py-2 text-sm text-black"
            @click="retryLogin()"
          >
            Try Again
          </button>
          <button
            class="rounded border border-white/20 px-4 py-2 text-sm text-horus-text-secondary"
            @click="$router.replace('/')"
          >
            Return Home
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
