---
name: Add Vue Component
description: >
  Guide to create a new reusable Vue component following the Horus design system
  with proper TypeScript types, TailwindCSS styling, and Vitest tests.
---

# Add a New Vue UI Component

Use this skill when creating a new reusable component for the Horus design system.

## Naming Convention

- **UI design system components**: `H` prefix → `HButton`, `HCard`, `HModal` — in `app/components/ui/`
- **Shared layout components**: no prefix → `AppHeader`, `AboutModal` — in `app/components/shared/`
- **Feature components**: no prefix, in feature dir → in `app/components/mission-hub/`, etc.

## Component Template

```vue
<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
    disabled?: boolean
  }>(),
  {
    variant: 'primary',
    size: 'md',
    disabled: false,
  },
)

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const classes = computed(() => [
  'base-classes-here',
  {
    'variant-primary-classes': props.variant === 'primary',
    'opacity-50 cursor-not-allowed': props.disabled,
  },
])
</script>

<template>
  <button :class="classes" :disabled="disabled" @click="emit('click', $event)">
    <slot />
  </button>
</template>
```

## Design System Colors

Use `horus-*` and `atc-*` tokens from `tailwind.config.ts`:

| Token | Use Case |
|-------|----------|
| `horus-primary` | Primary actions, accents |
| `horus-surface` | Card/panel backgrounds |
| `horus-border` | Borders and dividers |
| `atc-green` | Active/operational status |
| `atc-amber` | Warning status |
| `atc-red` | Error/critical status |

## Rules

1. Always use `<script setup lang="ts">` — never Options API
2. Never use `any` type — TypeScript strict mode
3. Never use inline styles — TailwindCSS classes only
4. Use `withDefaults` when props have default values

## Writing a Test

Create `app/components/ui/H<Component>.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HComponent from './HComponent.vue'

describe('HComponent', () => {
  it('renders with default props', () => {
    const wrapper = mount(HComponent)
    expect(wrapper.exists()).toBe(true)
  })

  it('emits click event', async () => {
    const wrapper = mount(HComponent)
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })
})
```

## Run After Creating

```bash
cd frontend
pnpm lint
pnpm test
```
