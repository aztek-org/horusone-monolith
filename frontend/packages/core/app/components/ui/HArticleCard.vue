<script setup lang="ts">
interface Props {
  title: string
  summary: string
  category?: string
  difficulty?: 'beginner' | 'intermediate' | 'advanced'
  tags?: string[]
  viewCount?: number
  slug: string
}

const props = withDefaults(defineProps<Props>(), {
  tags: () => [],
  viewCount: 0,
})

const emit = defineEmits<{
  navigate: [slug: string]
}>()

const difficultyVariant = computed(() => {
  switch (props.difficulty) {
    case 'advanced': return 'danger'
    case 'intermediate': return 'warning'
    default: return 'active'
  }
})

const difficultyLabel = computed(() => {
  switch (props.difficulty) {
    case 'advanced': return 'Advanced'
    case 'intermediate': return 'Intermediate'
    default: return 'Beginner'
  }
})

function handleClick() {
  emit('navigate', props.slug)
}
</script>

<template>
  <HCard
    variant="default"
    padding="md"
    hover
    class="cursor-pointer"
    @click="handleClick"
  >
    <div class="space-y-3">
      <!-- Title & Difficulty -->
      <div class="flex items-start justify-between gap-2">
        <h3 class="text-sm font-semibold text-horus-text-primary line-clamp-2">
          {{ title }}
        </h3>
        <HBadge
          v-if="difficulty"
          :variant="difficultyVariant"
          size="sm"
          class="flex-shrink-0"
        >
          {{ difficultyLabel }}
        </HBadge>
      </div>

      <!-- Summary -->
      <p class="text-xs text-horus-text-secondary line-clamp-3">
        {{ summary }}
      </p>

      <!-- Meta -->
      <div class="flex items-center justify-between text-xxs text-horus-text-muted">
        <div class="flex items-center gap-3">
          <span
            v-if="category"
            class="flex items-center gap-1"
          >
            <Icon
              name="heroicons:folder"
              class="w-3 h-3"
            />
            {{ category }}
          </span>
          <span
            v-if="viewCount > 0"
            class="flex items-center gap-1"
          >
            <Icon
              name="heroicons:eye"
              class="w-3 h-3"
            />
            {{ viewCount }}
          </span>
        </div>
      </div>

      <!-- Tags -->
      <div
        v-if="tags.length > 0"
        class="flex flex-wrap gap-1.5"
      >
        <span
          v-for="tag in tags.slice(0, 4)"
          :key="tag"
          class="inline-flex items-center px-1.5 py-0.5 rounded text-xxs bg-horus-bg-tertiary text-horus-text-muted border border-horus-border-subtle"
        >
          {{ tag }}
        </span>
        <span
          v-if="tags.length > 4"
          class="inline-flex items-center px-1.5 py-0.5 rounded text-xxs text-horus-text-muted"
        >
          +{{ tags.length - 4 }}
        </span>
      </div>
    </div>
  </HCard>
</template>
