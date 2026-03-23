<script setup lang="ts">
import type { LeaderboardEntry } from '~/composables/useGamification'

interface Props {
  entries: LeaderboardEntry[]
  currentUserId?: string | null
  showBadges?: boolean
}

withDefaults(defineProps<Props>(), {
  currentUserId: null,
  showBadges: true,
})

const medalEmojis: Record<number, string> = {
  1: '🥇',
  2: '🥈',
  3: '🥉',
}

function formatScore(score: number): string {
  return score.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

function formatHours(hours: number): string {
  return hours.toFixed(1)
}
</script>

<template>
  <HCard variant="elevated" padding="none">
    <div v-if="entries.length === 0" class="py-12 text-center">
      <Icon name="heroicons:trophy" class="w-10 h-10 text-horus-text-muted mx-auto mb-3" />
      <p class="text-sm text-horus-text-muted">No leaderboard data yet</p>
      <p class="text-xs text-horus-text-muted mt-1">Complete training sessions to appear on the leaderboard</p>
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr class="border-b border-horus-border-subtle">
            <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 w-14">
              Rank
            </th>
            <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-4 py-3">
              Pilot
            </th>
            <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 hidden sm:table-cell">
              Hours
            </th>
            <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 hidden md:table-cell">
              Scenarios
            </th>
            <th class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3">
              Score
            </th>
            <th
              v-if="showBadges"
              class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-3 py-3 hidden lg:table-cell"
            >
              Badges
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.user_id"
            :class="[
              'border-b border-horus-border-subtle last:border-0 transition-colors',
              entry.user_id === currentUserId
                ? 'bg-horus-accent-cyan/5 border-l-2 border-l-horus-accent-cyan'
                : entry.rank <= 3
                  ? 'bg-horus-bg-tertiary/30'
                  : 'hover:bg-horus-bg-tertiary/30',
            ]"
          >
            <!-- Rank -->
            <td class="px-3 py-3 text-center">
              <span v-if="entry.rank <= 3" class="text-lg">
                {{ medalEmojis[entry.rank] }}
              </span>
              <span v-else class="text-sm text-horus-text-muted font-mono">
                {{ entry.rank }}
              </span>
            </td>

            <!-- Pilot -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-3 min-w-0">
                <div class="w-8 h-8 rounded-full bg-horus-bg-tertiary border border-horus-border-subtle overflow-hidden flex-shrink-0">
                  <img
                    :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${entry.avatar_seed || entry.user_id}`"
                    :alt="entry.display_name"
                    class="w-full h-full object-cover"
                  />
                </div>
                <div class="min-w-0">
                  <p
                    :class="[
                      'text-sm font-medium truncate',
                      entry.user_id === currentUserId ? 'text-horus-accent-cyan' : 'text-horus-text-primary',
                    ]"
                  >
                    {{ entry.display_name || 'Unknown Pilot' }}
                    <span v-if="entry.user_id === currentUserId" class="text-xxs text-horus-accent-cyan ml-1">(You)</span>
                  </p>
                </div>
              </div>
            </td>

            <!-- Flight Hours -->
            <td class="px-3 py-3 text-center hidden sm:table-cell">
              <span class="text-sm text-horus-text-secondary font-mono">
                {{ formatHours(entry.flight_hours) }}h
              </span>
            </td>

            <!-- Scenarios -->
            <td class="px-3 py-3 text-center hidden md:table-cell">
              <span class="text-sm text-horus-text-secondary">
                {{ entry.scenarios_completed }}
              </span>
            </td>

            <!-- Score -->
            <td class="px-3 py-3 text-center">
              <span
                :class="[
                  'text-sm font-bold font-mono',
                  entry.rank === 1 ? 'text-yellow-400' : entry.rank <= 3 ? 'text-horus-accent-cyan' : 'text-horus-text-primary',
                ]"
              >
                {{ formatScore(entry.total_score) }}
              </span>
            </td>

            <!-- Badges -->
            <td
              v-if="showBadges"
              class="px-3 py-3 text-center hidden lg:table-cell"
            >
              <span class="inline-flex items-center gap-1 text-sm text-horus-text-secondary">
                <Icon name="heroicons:star" class="w-3.5 h-3.5 text-yellow-400" />
                {{ entry.badges_count }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </HCard>
</template>
