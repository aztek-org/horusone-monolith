<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: 'auth',
})
</script>

<template>
  <AppSettingsWorkspace
    title="Squawk Settings"
    subtitle="CONFIGURE YOUR PLATFORM OPERATIONS WORKSPACE"
    back-to="/dashboard"
    cancel-label="Back to Squawk"
    shortcuts-description="Customize platform oversight and admin shortcuts"
    voice-description="Configure voice defaults for platform review workflows"
    display-description="Tune platform dashboard preferences and density"
  />
</template>
