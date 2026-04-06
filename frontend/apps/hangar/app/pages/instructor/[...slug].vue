<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: 'auth',
})

const hasRedirected = ref(false)
const { user, isLoading } = useAuth()
const { resolveTargetApp, buildAppUrl } = useAuthRouting()

watch([isLoading, user], () => {
  if (hasRedirected.value || isLoading.value) {
    return
  }
  hasRedirected.value = true
  const targetApp = resolveTargetApp(user.value?.roles ?? [])
  if (targetApp === 'hangar') {
    navigateTo('/dashboard', { replace: true })
    return
  }
  window.location.href = buildAppUrl(targetApp, '/dashboard')
}, { immediate: true })
</script>

<template>
  <div class="min-h-screen bg-horus-bg-primary flex items-center justify-center">
    <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan" />
  </div>
</template>
