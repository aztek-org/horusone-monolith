<script setup lang="ts">
definePageMeta({
  layout: 'default'
})

const overallScore = ref(87)
const metrics = ref([
  { label: 'Decision Accuracy', value: 92, trend: 'up' },
  { label: 'Response Time', value: 78, trend: 'down' },
  { label: 'Procedural Compliance', value: 95, trend: 'stable' },
  { label: 'Communication Clarity', value: 84, trend: 'up' },
])

const recentSessions = ref([
  { id: '1', name: 'ETOPS Diversion Training', date: '2026-02-07', score: 88, duration: '45 min' },
  { id: '2', name: 'Engine Failure at V1', date: '2026-02-06', score: 92, duration: '32 min' },
  { id: '3', name: 'CAT III Approach', date: '2026-02-05', score: 78, duration: '28 min' },
])
</script>

<template>
  <NuxtLayout>
    <template #sidebar>
      <div class="space-y-6">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:calendar-days" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">TIME RANGE</h2>
        </div>
        
        <HButtonGroup
          model-value="week"
          :options="[
            { value: 'day', label: 'Day' },
            { value: 'week', label: 'Week' },
            { value: 'month', label: 'Month' }
          ]"
          size="sm"
        />
        
        <div class="pt-4 border-t border-horus-border-subtle space-y-4">
          <h3 class="text-xs font-semibold text-horus-text-secondary uppercase">Recent Sessions</h3>
          <div class="space-y-2">
            <div
              v-for="session in recentSessions"
              :key="session.id"
              class="p-3 rounded-lg bg-horus-bg-tertiary/50 hover:bg-horus-bg-tertiary transition-colors cursor-pointer"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm text-horus-text-primary truncate">{{ session.name }}</span>
                <span class="text-xs font-mono text-horus-accent-cyan">{{ session.score }}%</span>
              </div>
              <div class="flex items-center gap-2 text-xxs text-horus-text-muted">
                <span>{{ session.date }}</span>
                <span>•</span>
                <span>{{ session.duration }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    
    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <h1 class="text-xl font-semibold text-horus-text-primary">Performance Analytics</h1>
        
        <!-- Overall Score -->
        <HCard variant="elevated" padding="lg">
          <div class="flex flex-col md:flex-row md:items-center gap-6">
            <div class="flex-shrink-0">
              <div class="relative w-32 h-32">
                <svg class="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="8"
                    class="text-horus-bg-secondary"
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="8"
                    stroke-linecap="round"
                    class="text-horus-accent-cyan"
                    :stroke-dasharray="`${overallScore * 2.83} 283`"
                  />
                </svg>
                <div class="absolute inset-0 flex items-center justify-center">
                  <span class="text-3xl font-bold text-horus-text-primary">{{ overallScore }}</span>
                </div>
              </div>
            </div>
            <div class="flex-1">
              <h2 class="text-lg font-semibold text-horus-text-primary mb-2">Overall Performance Score</h2>
              <p class="text-sm text-horus-text-secondary">
                Your performance is above average. Focus on improving response time to reach expert level.
              </p>
            </div>
          </div>
        </HCard>
        
        <!-- Metrics Grid -->
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <HCard v-for="metric in metrics" :key="metric.label" variant="default" padding="md">
            <div class="space-y-2">
              <span class="text-xxs text-horus-text-muted uppercase">{{ metric.label }}</span>
              <div class="flex items-end justify-between">
                <span class="text-2xl font-bold text-horus-text-primary">{{ metric.value }}%</span>
                <Icon 
                  :name="metric.trend === 'up' ? 'heroicons:arrow-trending-up' : metric.trend === 'down' ? 'heroicons:arrow-trending-down' : 'heroicons:minus'"
                  :class="[
                    'w-5 h-5',
                    metric.trend === 'up' && 'text-horus-status-success',
                    metric.trend === 'down' && 'text-horus-status-danger',
                    metric.trend === 'stable' && 'text-horus-text-muted'
                  ]"
                />
              </div>
              <HProgress :value="metric.value" :show-percentage="false" size="sm" />
            </div>
          </HCard>
        </div>
        
        <!-- Chart Placeholder -->
        <HCard variant="glass" padding="lg">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-horus-text-primary">Performance Trend</h3>
            <HButtonGroup
              model-value="score"
              :options="[
                { value: 'score', label: 'Score' },
                { value: 'time', label: 'Time' }
              ]"
              size="sm"
            />
          </div>
          <div class="h-64 flex items-center justify-center border border-dashed border-horus-border-subtle rounded-lg">
            <div class="text-center text-horus-text-muted">
              <Icon name="heroicons:chart-bar" class="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p class="text-sm">Chart visualization</p>
              <p class="text-xs">Coming soon</p>
            </div>
          </div>
        </HCard>
      </div>
    </template>
    
    <template #panel>
      <div class="space-y-6">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:trophy" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">ACHIEVEMENTS</h2>
        </div>
        
        <div class="space-y-3">
          <div class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-success/10 border border-horus-status-success/30">
            <Icon name="heroicons:star-solid" class="w-8 h-8 text-horus-status-success" />
            <div>
              <p class="text-sm font-medium text-horus-text-primary">Decision Master</p>
              <p class="text-xxs text-horus-text-muted">90%+ accuracy in 5 sessions</p>
            </div>
          </div>
          
          <div class="flex items-center gap-3 p-3 rounded-lg bg-horus-accent-cyan/10 border border-horus-accent-cyan/30">
            <Icon name="heroicons:bolt-solid" class="w-8 h-8 text-horus-accent-cyan" />
            <div>
              <p class="text-sm font-medium text-horus-text-primary">Quick Responder</p>
              <p class="text-xxs text-horus-text-muted">Sub-5s average response</p>
            </div>
          </div>
          
          <div class="flex items-center gap-3 p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle opacity-50">
            <Icon name="heroicons:fire" class="w-8 h-8 text-horus-text-muted" />
            <div>
              <p class="text-sm font-medium text-horus-text-secondary">Streak Master</p>
              <p class="text-xxs text-horus-text-muted">7-day training streak</p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
