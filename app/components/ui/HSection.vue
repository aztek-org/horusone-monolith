<script setup lang="ts">
interface Props {
  icon?: string
  title?: string
  collapsible?: boolean
  defaultExpanded?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  collapsible: false,
  defaultExpanded: true
})

const isExpanded = ref(props.defaultExpanded)

function toggle() {
  if (props.collapsible) {
    isExpanded.value = !isExpanded.value
  }
}
</script>

<template>
  <div class="space-y-3">
    <button
      v-if="title"
      :class="[
        'flex items-center gap-2 w-full text-left',
        collapsible && 'cursor-pointer hover:text-horus-text-primary'
      ]"
      :disabled="!collapsible"
      @click="toggle"
    >
      <Icon v-if="icon" :name="icon" class="w-4 h-4 text-horus-accent-cyan" />
      <span class="text-xs font-semibold uppercase tracking-wider text-horus-text-secondary flex-1">
        {{ title }}
      </span>
      <Icon
        v-if="collapsible"
        name="heroicons:chevron-down-20-solid"
        :class="[
          'w-4 h-4 text-horus-text-muted transition-transform duration-200',
          !isExpanded && '-rotate-90'
        ]"
      />
    </button>
    
    <div
      v-show="!collapsible || isExpanded"
      :class="['space-y-2', collapsible && 'animate-fade-in']"
    >
      <slot />
    </div>
  </div>
</template>
