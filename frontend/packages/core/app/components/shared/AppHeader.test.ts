import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AppHeader from './AppHeader.vue'

const mocks = vi.hoisted(() => ({
  route: { path: '/', name: undefined as string | undefined },
  aiParams: null as null | { value: { isOnline: boolean } },
}))

vi.mock('#app/composables/router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  navigateTo: vi.fn(),
  defineNuxtRouteMiddleware: (fn: unknown) => fn,
}))

vi.mock('../../composables/useAICopilot', async () => {
  const { ref } = await import('vue')
  mocks.aiParams = ref({ isOnline: true })
  return { useAICopilot: () => ({ params: mocks.aiParams }) }
})

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
      HButton: { template: '<button><slot /></button>' },
      HStatusPill: {
        props: ['online', 'label'],
        template: '<span class="status-pill">{{ label }}</span>',
      },
    },
  },
}

describe('AppHeader', () => {
  beforeEach(() => {
    mocks.route.path = '/'
    mocks.route.name = undefined
    if (mocks.aiParams) mocks.aiParams.value.isOnline = true
  })

  it('renders the title for an exact route match', () => {
    mocks.route.path = '/dashboard'
    const wrapper = mount(AppHeader, globalStubs)
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('HORUS v0.2')
  })

  it('renders the title for a prefixed route match', () => {
    mocks.route.path = '/library/principles-of-flight'
    const wrapper = mount(AppHeader, globalStubs)
    expect(wrapper.text()).toContain('Library')
  })

  it('falls back to a title-cased route name for unknown paths', () => {
    mocks.route.path = '/unknown'
    mocks.route.name = 'flight-debrief'
    const wrapper = mount(AppHeader, globalStubs)
    expect(wrapper.text()).toContain('Flight Debrief')
  })

  it('shows the AI ready label when the co-processor is online', () => {
    if (mocks.aiParams) mocks.aiParams.value.isOnline = true
    const wrapper = mount(AppHeader, globalStubs)
    expect(wrapper.text()).toContain('AI CO-PROCESSOR READY')
  })

  it('shows the AI offline label when the co-processor is offline', () => {
    if (mocks.aiParams) mocks.aiParams.value.isOnline = false
    const wrapper = mount(AppHeader, globalStubs)
    expect(wrapper.text()).toContain('AI OFFLINE')
  })

  it('renders the default execute simulation action', () => {
    const wrapper = mount(AppHeader, globalStubs)
    expect(wrapper.text()).toContain('EXECUTE SIMULATION')
  })

  it('renders the action slot override', () => {
    const wrapper = mount(AppHeader, {
      ...globalStubs,
      slots: { action: '<button class="custom-action">CUSTOM</button>' },
    })
    expect(wrapper.find('.custom-action').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('EXECUTE SIMULATION')
  })
})
