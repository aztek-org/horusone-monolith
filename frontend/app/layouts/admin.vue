<script setup lang="ts">
// Admin layout: AppHeader + sidebar + main content area
</script>

<template>
  <div class="flex flex-col min-h-screen bg-horus-bg-primary">
    <AppHeader title="Horus Admin" subtitle="PLATFORM MANAGEMENT" />

    <div class="flex-1 flex overflow-hidden">
      <AdminSidebar class="hidden lg:flex lg:flex-col" />

      <main class="flex-1 overflow-y-auto p-4 lg:p-6">
        <slot />
      </main>
    </div>
  </div>
</template>
