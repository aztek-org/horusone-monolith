import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import HShortcutsModal from './HShortcutsModal.vue'

// ---------------------------------------------------------------------------
// Stubs for Nuxt auto-imported components and composables
// ---------------------------------------------------------------------------

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span />' },
      NuxtIcon: { template: '<span />' },
      NuxtLink: { template: '<a><slot /></a>' },
      Teleport: { template: '<div><slot /></div>' },
    },
  },
}

// Mock the composable — returns a static set of shortcuts for testing
vi.mock('../../composables/useKeyboardShortcuts', () => ({
  useKeyboardShortcuts: () => ({
    shortcuts: {
      value: {
        push_to_talk: {
          key: 'KeyB',
          modifiers: { ctrl: false, shift: false, alt: false },
          label: 'Push to Talk',
          description: 'Press and hold to communicate with ATC',
          category: 'voice',
          action: null,
          enabled: true,
        },
        nav_dashboard: {
          key: 'KeyD',
          modifiers: { ctrl: true, shift: false, alt: false },
          label: 'Go to Dashboard',
          description: 'Navigate to the Dashboard page',
          category: 'navigation',
          action: null,
          enabled: true,
        },
        escape: {
          key: 'Escape',
          modifiers: { ctrl: false, shift: false, alt: false },
          label: 'Close / Cancel',
          description: 'Close modal or cancel current action',
          category: 'general',
          action: null,
          enabled: true,
        },
      },
    },
    getDisplayCombo: (id: string) => {
      const combos: Record<string, string> = {
        push_to_talk: 'B',
        nav_dashboard: 'Ctrl+D',
        escape: 'Esc',
      }
      return combos[id] ?? ''
    },
  }),
}))

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HShortcutsModal', () => {
  it('renders nothing when modelValue is false', () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: false },
    })

    expect(wrapper.find('[class*="fixed"]').exists()).toBe(false)
  })

  it('renders the modal overlay when modelValue is true', () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: true },
    })

    expect(wrapper.text()).toContain('Keyboard Shortcuts')
    expect(wrapper.text()).toContain('Quick Reference')
  })

  it('displays shortcut categories and items', () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: true },
    })

    // Category headings
    expect(wrapper.text()).toContain('Voice')
    expect(wrapper.text()).toContain('Navigation')
    expect(wrapper.text()).toContain('General')

    // Shortcut labels
    expect(wrapper.text()).toContain('Push to Talk')
    expect(wrapper.text()).toContain('Go to Dashboard')
    expect(wrapper.text()).toContain('Close / Cancel')
  })

  it('displays key combo badges from getDisplayCombo', () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: true },
    })

    const kbds = wrapper.findAll('kbd')
    const kbdTexts = kbds.map(k => k.text())

    // "B" for push_to_talk
    expect(kbdTexts).toContain('B')
    // "Ctrl" and "D" for nav_dashboard (split by "+")
    expect(kbdTexts).toContain('Ctrl')
    expect(kbdTexts).toContain('D')
    // "Esc" for escape
    expect(kbdTexts).toContain('Esc')
  })

  it('emits update:modelValue(false) when close button is clicked', async () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: true },
    })

    // The close button is the button inside the header with the x-mark icon
    const closeButton = wrapper.find('button')
    await closeButton.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
  })

  it('emits update:modelValue(false) when backdrop is clicked', async () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: true },
    })

    // The backdrop is the outermost fixed div
    const backdrop = wrapper.find('[class*="fixed"]')
    await backdrop.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
  })

  it('shows a link to Settings in the footer', () => {
    const wrapper = mount(HShortcutsModal, {
      ...globalStubs,
      props: { modelValue: true },
    })

    expect(wrapper.text()).toContain('Settings')
  })
})
