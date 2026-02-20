<script setup lang="ts">
definePageMeta({
  layout: 'default'
})

const scenarios = ref([
  { id: '1', name: 'Engine Failure at V1', type: 'Emergency', difficulty: 'Expert', created: '2026-02-01' },
  { id: '2', name: 'CAT III Autoland', type: 'Approach', difficulty: 'Proficient', created: '2026-02-03' },
  { id: '3', name: 'Oceanic ETOPS Diversion', type: 'Navigation', difficulty: 'Expert', created: '2026-02-05' },
  { id: '4', name: 'Windshear Recovery', type: 'Weather', difficulty: 'Proficient', created: '2026-02-06' },
  { id: '5', name: 'Rapid Decompression', type: 'Emergency', difficulty: 'Expert', created: '2026-02-07' },
])

function getDifficultyVariant(difficulty: string) {
  switch (difficulty) {
    case 'Expert': return 'danger'
    case 'Proficient': return 'warning'
    default: return 'active'
  }
}
</script>

<template>
  <NuxtLayout>
    <template #sidebar>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:funnel" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">FILTERS</h2>
        </div>
        
        <div class="space-y-3">
          <HDropdown
            model-value=""
            :options="[
              { value: 'all', label: 'All Types' },
              { value: 'emergency', label: 'Emergency' },
              { value: 'approach', label: 'Approach' },
              { value: 'navigation', label: 'Navigation' },
              { value: 'weather', label: 'Weather' }
            ]"
            label="Scenario Type"
            placeholder="Select type"
          />
          
          <HDropdown
            model-value=""
            :options="[
              { value: 'all', label: 'All Levels' },
              { value: 'novice', label: 'Novice' },
              { value: 'proficient', label: 'Proficient' },
              { value: 'expert', label: 'Expert' }
            ]"
            label="Difficulty"
            placeholder="Select difficulty"
          />
        </div>
      </div>
    </template>
    
    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <div class="flex items-center justify-between">
          <h1 class="text-xl font-semibold text-horus-text-primary">Scenario Library</h1>
          <HButton variant="primary" size="sm" icon="heroicons:plus">
            New Scenario
          </HButton>
        </div>
        
        <!-- Scenarios Grid -->
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <HCard 
            v-for="scenario in scenarios" 
            :key="scenario.id"
            variant="default"
            padding="md"
            hover
            class="cursor-pointer"
          >
            <div class="space-y-3">
              <div class="flex items-start justify-between">
                <h3 class="text-sm font-semibold text-horus-text-primary">{{ scenario.name }}</h3>
                <HBadge :variant="getDifficultyVariant(scenario.difficulty)" size="sm">
                  {{ scenario.difficulty }}
                </HBadge>
              </div>
              
              <div class="flex items-center gap-4 text-xs text-horus-text-muted">
                <span class="flex items-center gap-1">
                  <Icon name="heroicons:tag" class="w-3 h-3" />
                  {{ scenario.type }}
                </span>
                <span class="flex items-center gap-1">
                  <Icon name="heroicons:calendar" class="w-3 h-3" />
                  {{ scenario.created }}
                </span>
              </div>
              
              <div class="flex gap-2 pt-2">
                <HButton variant="ghost" size="sm" class="flex-1">
                  <Icon name="heroicons:eye" class="w-4 h-4" />
                  Preview
                </HButton>
                <HButton variant="secondary" size="sm" class="flex-1">
                  <Icon name="heroicons:play" class="w-4 h-4" />
                  Run
                </HButton>
              </div>
            </div>
          </HCard>
        </div>
      </div>
    </template>
    
    <template #panel>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">QUICK STATS</h2>
        </div>
        
        <div class="space-y-3">
          <HDataPanel value="12" label="Total Scenarios" variant="compact" />
          <HDataPanel value="8" label="Completed" variant="compact" />
          <HDataPanel value="4" label="In Progress" variant="compact" />
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
