<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: 'auth',
})
</script>

<template>
  <AppSettingsWorkspace
    title="Tower Settings"
    subtitle="CONFIGURE YOUR TOWER OPERATIONS WORKSPACE"
    back-to="/dashboard"
    cancel-label="Back to Tower"
    shortcuts-description="Customize controller and operations shortcuts"
    voice-description="Configure controller voice communication defaults"
    display-description="Tune dashboard density and theme preferences"
  />
</template>
