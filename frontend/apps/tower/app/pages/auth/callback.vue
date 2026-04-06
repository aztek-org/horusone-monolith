<script setup lang="ts">
/**
 * Tower OIDC callback page.
 */
defineOptions({
  name: 'TowerAuthCallbackPage',
})

definePageMeta({
  layout: false,
  ssr: false,
})

const { handleCallback, login, isAuthenticated, error, user } = useAuth()
const router = useRouter()
const { resolveTargetApp, isCurrentApp, resolveSafeRedirect, buildAppUrl, getFallbackRoute } = useAuthRouting()

onMounted(async () => {
  await handleCallback()

  if (isAuthenticated.value && user.value) {
    const targetApp = resolveTargetApp(user.value.roles)
    const redirect = resolveSafeRedirect(sessionStorage.getItem('auth_redirect'), targetApp)
    sessionStorage.removeItem('auth_redirect')

    if (!isCurrentApp(targetApp)) {
      window.location.replace(
        buildAppUrl(targetApp, '/login', {
          redirect,
          auto: '1',
          handoff: '1',
        }),
      )
      return
    }

    await router.replace(redirect)
    if (router.currentRoute.value.path === '/auth/callback') {
      await router.replace(getFallbackRoute(targetApp))
    }
  }
})

function retryLogin(): void {
  const redirect = sessionStorage.getItem('auth_redirect')
  login(resolveSafeRedirect(redirect))
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
            @click="$router.replace('/login')"
          >
            Return Login
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
