<script setup lang="ts">
definePageMeta({
  layout: false,
  middleware: 'auth',
})
</script>

<template>
  <AppSettingsWorkspace
    title="Hangar Settings"
    subtitle="CONFIGURE YOUR PILOT EXPERIENCE"
    back-to="/"
    cancel-label="Back to Hangar"
  />
</template>
