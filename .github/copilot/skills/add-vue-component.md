# Skill: Add a New Vue UI Component

Use this skill when creating a new reusable component for the Horus design system.

## Naming Convention

- **UI design system components**: `H` prefix → `HButton`, `HCard`, `HModal`
  - Location: `app/components/ui/`
- **Shared layout components**: no prefix → `AppHeader`, `AboutModal`
  - Location: `app/components/shared/`
- **Feature components**: no prefix, in feature dir → `FlightDynamics`
  - Location: `app/components/mission-hub/`, `app/components/scenario-architect/`

## Component Template

```vue
<script setup lang="ts">
// Props — always use defineProps with explicit TypeScript interface
const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
    disabled?: boolean
    label?: string
  }>(),
  {
    variant: 'primary',
    size: 'md',
    disabled: false,
  },
)

// Emits — always explicitly typed
const emit = defineEmits<{
  click: [event: MouseEvent]
  change: [value: string]
}>()

// Computed styles using TailwindCSS classes
const classes = computed(() => [
  'base-classes-here',
  {
    'variant-primary-classes': props.variant === 'primary',
    'variant-secondary-classes': props.variant === 'secondary',
    'opacity-50 cursor-not-allowed': props.disabled,
  },
])
</script>

<template>
  <button
    :class="classes"
    :disabled="disabled"
    @click="emit('click', $event)"
  >
    <slot />
  </button>
</template>
```

## Design System Colors (from `tailwind.config.ts`)

Use `horus-*` and `atc-*` color tokens, not raw Tailwind colors:

| Token | Use Case |
|-------|----------|
| `horus-primary` | Primary actions, accents |
| `horus-surface` | Card/panel backgrounds |
| `horus-border` | Borders and dividers |
| `atc-green` | Active/operational status |
| `atc-amber` | Warning status |
| `atc-red` | Error/critical status |

## Rules

1. **Always** use `<script setup lang="ts">` — never Options API or setup() function
2. **Never** use `any` type — TypeScript strict mode
3. **Never** use inline styles — TailwindCSS classes only
4. Use `withDefaults` when props have default values
5. Expose only what's needed — use `defineExpose` sparingly
6. Component files and their names must match exactly (case-sensitive)

## Writing a Test for the Component

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

  it('applies correct class for variant', () => {
    const wrapper = mount(HComponent, {
      props: { variant: 'secondary' },
    })
    expect(wrapper.classes()).toContain('expected-class')
  })

  it('emits click event', async () => {
    const wrapper = mount(HComponent)
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('is disabled when disabled prop is true', () => {
    const wrapper = mount(HComponent, {
      props: { disabled: true },
    })
    expect(wrapper.attributes('disabled')).toBeDefined()
  })
})
```

## Run After Creating

```bash
cd frontend
pnpm lint
pnpm test
```
