import { describe, it, expect, vi, beforeEach } from 'vitest'

import adminMiddleware from './admin'

const mocks = vi.hoisted(() => ({
  isAuthenticated: { value: true },
  hasAnyRole: vi.fn<(roles: string[]) => boolean>(() => true),
  navigateTo: vi.fn((to: unknown) => ({ redirectedTo: to })),
}))

vi.mock('#app/composables/router', () => ({
  useRoute: vi.fn(),
  useRouter: vi.fn(),
  navigateTo: mocks.navigateTo,
  defineNuxtRouteMiddleware: (fn: unknown) => fn,
}))

vi.mock('../composables/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: mocks.isAuthenticated,
    hasAnyRole: (...roles: string[]) => mocks.hasAnyRole(roles),
  }),
}))

const run = () => (adminMiddleware as unknown as () => unknown)()

describe('admin middleware', () => {
  beforeEach(() => {
    mocks.navigateTo.mockClear()
    mocks.hasAnyRole.mockReset()
    mocks.hasAnyRole.mockReturnValue(true)
    mocks.isAuthenticated.value = true
  })

  it('allows platform-admin and org-admin users through', () => {
    const result = run()
    expect(result).toBeUndefined()
    expect(mocks.navigateTo).not.toHaveBeenCalled()
    expect(mocks.hasAnyRole).toHaveBeenCalledWith(['platform-admin', 'org-admin'])
  })

  it('redirects unauthenticated users to /login with an /admin redirect', () => {
    mocks.isAuthenticated.value = false
    const result = run()
    expect(mocks.navigateTo).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/admin' },
    })
    expect(result).toEqual({
      redirectedTo: { path: '/login', query: { redirect: '/admin' } },
    })
  })

  it('redirects authenticated users lacking the roles to /dashboard', () => {
    mocks.hasAnyRole.mockReturnValue(false)
    const result = run()
    expect(mocks.navigateTo).toHaveBeenCalledWith({
      path: '/dashboard',
      query: { error: 'insufficient-permissions' },
    })
    expect(result).toEqual({
      redirectedTo: { path: '/dashboard', query: { error: 'insufficient-permissions' } },
    })
  })
})
