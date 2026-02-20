<script setup lang="ts">
// Redirect to configurator on app root
definePageMeta({
  redirect: '/configurator'
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center space-y-4">
      <Icon name="svg-spinners:ring-resize" class="w-12 h-12 text-horus-accent-cyan mx-auto" />
      <p class="text-horus-text-secondary">Loading...</p>
    </div>
  </div>
</template>
