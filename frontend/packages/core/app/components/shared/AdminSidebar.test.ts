import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdminSidebar from './AdminSidebar.vue'

const mocks = vi.hoisted(() => ({
  roles: [] as string[],
  route: { path: '/admin', fullPath: '/admin' },
}))

vi.mock('#app/composables/router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  navigateTo: vi.fn(),
  defineNuxtRouteMiddleware: (fn: unknown) => fn,
}))

vi.mock('../../composables/useAuth', async () => {
  const { ref } = await import('vue')
  return {
    useAuth: () => ({
      isAuthenticated: ref(true),
      hasAnyRole: (...roles: string[]) => mocks.roles.some(role => roles.includes(role)),
    }),
  }
})

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
      NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
    },
  },
}

describe('AdminSidebar', () => {
  beforeEach(() => {
    mocks.roles = []
    mocks.route.path = '/admin'
    mocks.route.fullPath = '/admin'
  })

  it('shows the platform-admin-only management links to platform admins', () => {
    mocks.roles = ['platform-admin']
    const wrapper = mount(AdminSidebar, globalStubs)

    expect(wrapper.text()).toContain('Organizations')
    expect(wrapper.text()).toContain('Users')
  })

  it('hides platform-admin-only links from org-admins', () => {
    mocks.roles = ['org-admin']
    const wrapper = mount(AdminSidebar, globalStubs)

    expect(wrapper.text()).not.toContain('Organizations')
    expect(wrapper.text()).not.toContain('Users')
  })

  it('keeps Overview, Modules and Leaderboard for org-admins', () => {
    mocks.roles = ['org-admin']
    const wrapper = mount(AdminSidebar, globalStubs)

    expect(wrapper.text()).toContain('Overview')
    expect(wrapper.text()).toContain('Modules')
    expect(wrapper.text()).toContain('Leaderboard')
  })

  it('keeps the Instructor link for instructor/org-admin roles', () => {
    mocks.roles = ['org-admin']
    const wrapper = mount(AdminSidebar, globalStubs)

    expect(wrapper.text()).toContain('Instructor')
  })
})
