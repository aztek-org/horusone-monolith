<script setup lang="ts">
import type { BadgeTier, BadgeCategory } from '~/composables/useGamification'

interface Props {
  name: string
  description: string
  icon: string
  tier: BadgeTier
  category: BadgeCategory
  earned: boolean
  earnedAt?: string | null
  progress?: number
}

const props = withDefaults(defineProps<Props>(), {
  earnedAt: null,
  progress: 0,
})

const tierConfig: Record<BadgeTier, { color: string, bg: string, border: string, label: string }> = {
  bronze: {
    color: 'text-amber-600',
    bg: 'bg-amber-600/10',
    border: 'border-amber-600/30',
    label: 'Bronze',
  },
  silver: {
    color: 'text-gray-300',
    bg: 'bg-gray-300/10',
    border: 'border-gray-300/30',
    label: 'Silver',
  },
  gold: {
    color: 'text-yellow-400',
    bg: 'bg-yellow-400/10',
    border: 'border-yellow-400/30',
    label: 'Gold',
  },
  platinum: {
    color: 'text-blue-200',
    bg: 'bg-blue-200/10',
    border: 'border-blue-200/30',
    label: 'Platinum',
  },
}

const currentTier = computed(() => tierConfig[props.tier])

const categoryLabels: Record<BadgeCategory, string> = {
  flight: 'Flight',
  communication: 'Communication',
  knowledge: 'Knowledge',
  streak: 'Streak',
  achievement: 'Achievement',
}

function formatEarnedDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}
</script>

<template>
  <div
    :class="[
      'relative rounded-lg border p-4 transition-all duration-300',
      earned
        ? `${currentTier.border} bg-horus-bg-elevated/90 shadow-card-elevated`
        : 'border-horus-border-subtle bg-horus-bg-card/50 opacity-60',
      earned && 'hover:shadow-glow-cyan/10 hover:border-horus-accent-cyan/30',
    ]"
  >
    <!-- Glow effect for earned badges -->
    <div
      v-if="earned"
      class="absolute inset-0 rounded-lg animate-glow opacity-20 pointer-events-none"
    />

    <!-- Badge Content -->
    <div class="relative space-y-3">
      <!-- Icon & Tier -->
      <div class="flex items-start justify-between">
        <div
          :class="[
            'w-12 h-12 rounded-xl flex items-center justify-center text-2xl',
            earned ? currentTier.bg : 'bg-horus-bg-tertiary',
          ]"
        >
          <span v-if="earned">{{ icon }}</span>
          <Icon
            v-else
            name="heroicons:lock-closed"
            class="w-5 h-5 text-horus-text-muted"
          />
        </div>

        <!-- Tier Badge -->
        <span
          :class="[
            'inline-flex items-center px-2 py-0.5 rounded text-xxs font-bold uppercase tracking-wider border',
            earned
              ? `${currentTier.color} ${currentTier.bg} ${currentTier.border}`
              : 'text-horus-text-muted bg-horus-bg-tertiary border-horus-border-subtle',
          ]"
        >
          {{ currentTier.label }}
        </span>
      </div>

      <!-- Name & Description -->
      <div>
        <h4
          :class="[
            'text-sm font-semibold',
            earned ? 'text-horus-text-primary' : 'text-horus-text-muted',
          ]"
        >
          {{ name }}
        </h4>
        <p class="text-xs text-horus-text-secondary mt-1 line-clamp-2">
          {{ description }}
        </p>
      </div>

      <!-- Category -->
      <div class="flex items-center gap-1.5">
        <span class="text-xxs text-horus-text-muted uppercase tracking-wider">
          {{ categoryLabels[category] }}
        </span>
      </div>

      <!-- Earned Date or Progress -->
      <div
        v-if="earned && earnedAt"
        class="flex items-center gap-1.5 text-xs text-horus-status-success"
      >
        <Icon
          name="heroicons:check-circle"
          class="w-4 h-4"
        />
        <span>Earned {{ formatEarnedDate(earnedAt) }}</span>
      </div>

      <div
        v-else-if="!earned && progress > 0"
        class="space-y-1.5"
      >
        <div class="flex items-center justify-between text-xxs">
          <span class="text-horus-text-muted">Progress</span>
          <span class="font-mono text-horus-text-secondary">{{ Math.round(progress) }}%</span>
        </div>
        <div class="w-full h-1.5 rounded-full bg-horus-bg-secondary overflow-hidden">
          <div
            class="h-full rounded-full bg-horus-accent-cyan/60 transition-all duration-500"
            :style="{ width: `${Math.min(100, Math.max(0, progress))}%` }"
          />
        </div>
      </div>
    </div>
  </div>
</template>
