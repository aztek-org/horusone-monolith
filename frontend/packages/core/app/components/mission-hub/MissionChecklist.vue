<script setup lang="ts">
const { items, autoGenEnabled, toggleAutoGen } = useChecklist()

const diversionItems = computed(() =>
  items.value.filter(item => item.category === 'DIVERSION'),
)
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon
          name="heroicons:clipboard-document-list"
          class="w-5 h-5 text-horus-accent-cyan"
        />
        <h2 class="text-sm font-semibold text-horus-text-primary">
          LIVE MISSION CHECKLIST
        </h2>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xxs text-horus-text-muted">AUTO-GEN</span>
        <button
          :class="[
            'relative w-8 h-4 rounded-full transition-colors',
            autoGenEnabled ? 'bg-horus-accent-cyan' : 'bg-horus-bg-tertiary',
          ]"
          @click="toggleAutoGen"
        >
          <span
            :class="[
              'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform',
              autoGenEnabled ? 'left-4' : 'left-0.5',
            ]"
          />
        </button>
      </div>
    </div>

    <!-- Current Phase -->
    <div class="p-2 rounded-lg bg-horus-status-warning/10 border border-horus-status-warning/30">
      <span class="text-xxs text-horus-text-muted">CURRENT PHASE:</span>
      <span class="text-xs font-semibold text-horus-status-warning ml-2">DIVERSION</span>
    </div>

    <!-- Checklist Items -->
    <div class="space-y-1">
      <HChecklistItem
        v-for="item in diversionItems"
        :key="item.id"
        :title="item.title"
        :subtitle="item.subtitle"
        :status="item.status"
        :meta="item.meta"
      />
    </div>
  </div>
</template>
