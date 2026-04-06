<script setup lang="ts">
/**
 * Squawk login-only page.
 */
defineOptions({
  name: 'SquawkLoginPage',
})

definePageMeta({
  layout: false,
  ssr: false,
})

const { login, isAuthenticated, isLoading, user } = useAuth()
const route = useRoute()
const router = useRouter()
const {
  resolveSafeRedirect,
  resolveTargetApp,
  isCurrentApp,
  buildAppUrl,
  buildGatewayLoginUrl,
  shouldRedirectToGatewayLogin,
} = useAuthRouting()

const hasAutoLoginStarted = ref(false)
const redirectPath = computed(() => resolveSafeRedirect(route.query.redirect))
const isHandoff = computed(() => route.query.handoff === '1')
const shouldAutoLogin = computed(() => {
  const auto = route.query.auto
  return auto === '1' || auto === 'true'
})

watch(
  () => [isAuthenticated.value, isLoading.value, user.value] as const,
  ([authed, loading, currentUser]) => {
    if (loading || !authed || !currentUser) return

    const targetApp = resolveTargetApp(currentUser.roles)
    const redirect = redirectPath.value

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

    void router.replace(redirect)
  },
  { immediate: true },
)

watch(
  () => [isLoading.value, isAuthenticated.value] as const,
  ([loading, authed]) => {
    if (loading || authed || !shouldAutoLogin.value || hasAutoLoginStarted.value) return
    hasAutoLoginStarted.value = true
    login(redirectPath.value)
  },
  { immediate: true },
)

onMounted(() => {
  if (isAuthenticated.value) return
  if (shouldRedirectToGatewayLogin(isHandoff.value)) {
    window.location.replace(buildGatewayLoginUrl(redirectPath.value))
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-horus-bg-primary">
    <div class="w-full max-w-md rounded-xl border border-white/10 bg-horus-bg-secondary p-8 text-center">
      <NuxtImg
        src="/horusone_logo.png"
        alt="Horus"
        class="mx-auto mb-2 h-16"
        loading="eager"
        width="200"
        height="64"
      />
      <p class="mb-8 text-sm text-horus-text-secondary">
        AI-Powered Aviation Training Platform
      </p>

      <button
        class="w-full rounded-lg bg-horus-accent-cyan px-6 py-3 font-medium text-black transition-colors hover:bg-horus-accent-cyan/90"
        @click="login(redirectPath)"
      >
        Sign in with SSO
      </button>
    </div>
  </div>
</template>
