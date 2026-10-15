import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AppSidebar from './AppSidebar.vue'

const mocks = vi.hoisted(() => ({
  auth: null as null | {
    user: { value: { displayName: string, email: string, keycloakId: string } }
    isAuthenticated: { value: boolean }
    hasAnyRole: ReturnType<typeof vi.fn>
    login: ReturnType<typeof vi.fn>
    logout: ReturnType<typeof vi.fn>
  },
  route: { path: '/configurator', fullPath: '/configurator' },
}))

vi.mock('#app/composables/router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  navigateTo: vi.fn(),
  defineNuxtRouteMiddleware: (fn: unknown) => fn,
}))

// The public-asset virtual module (`/logo.svg`) resolves through this helper,
// which normally requires a live Nuxt app config.
vi.mock('#internal/nuxt/paths', () => ({
  publicAssetsURL: (path: string) => path,
  buildAssetsURL: (path: string) => path,
  appAssetsURL: (path: string) => path,
}))

vi.mock('../../composables/useAuth', async () => {
  const { ref } = await import('vue')
  mocks.auth = {
    user: ref({ displayName: 'Maverick', email: 'maverick@horus.app', keycloakId: 'kc-1' }),
    isAuthenticated: ref(true),
    hasAnyRole: vi.fn(() => true),
    login: vi.fn(),
    logout: vi.fn(),
  }
  return { useAuth: () => mocks.auth }
})

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
      NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      ClientOnly: { template: '<div><slot /></div>' },
      Transition: { template: '<div><slot /></div>' },
      AboutModal: { template: '<div class="about-modal" />' },
      HButton: { template: '<button><slot /></button>' },
    },
  },
}

describe('AppSidebar', () => {
  beforeEach(() => {
    if (mocks.auth) {
      mocks.auth.isAuthenticated.value = true
      mocks.auth.hasAnyRole.mockReturnValue(true)
    }
    mocks.route.path = '/configurator'
    mocks.route.fullPath = '/configurator'
  })

  it('renders the brand and base navigation groups when authenticated', () => {
    const wrapper = mount(AppSidebar, globalStubs)
    expect(wrapper.text()).toContain('Horus Aviation')
    expect(wrapper.text()).toContain('Training')
    expect(wrapper.text()).toContain('Learning')
    expect(wrapper.text()).toContain('Progress')
  })

  it('renders role-gated management links when the user has the roles', () => {
    const wrapper = mount(AppSidebar, globalStubs)
    expect(wrapper.text()).toContain('Management')
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Instructor')
    expect(wrapper.text()).toContain('Admin')
  })

  it('hides the management group when roles do not match', () => {
    if (mocks.auth) mocks.auth.hasAnyRole.mockReturnValue(false)
    const wrapper = mount(AppSidebar, globalStubs)
    expect(wrapper.text()).not.toContain('Management')
  })

  it('shows the login prompt when unauthenticated', () => {
    if (mocks.auth) mocks.auth.isAuthenticated.value = false
    const wrapper = mount(AppSidebar, globalStubs)
    expect(wrapper.text()).toContain('Sign in to access navigation')
    expect(wrapper.text()).toContain('Login')
  })

  it('renders the user display name and calls logout', async () => {
    const wrapper = mount(AppSidebar, globalStubs)
    expect(wrapper.text()).toContain('Maverick')
    expect(wrapper.text()).toContain('maverick@horus.app')
    await wrapper.find('button[title="Logout"]').trigger('click')
    expect(mocks.auth?.logout).toHaveBeenCalled()
  })

  it('collapses to an icon rail with aria labels when collapsed', () => {
    const wrapper = mount(AppSidebar, { ...globalStubs, props: { collapsed: true } })
    expect(wrapper.find('aside').classes()).toContain('w-16')
    expect(wrapper.find('a[aria-label="Configurator"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Horus Aviation')
  })
})
