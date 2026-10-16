import { describe, it, expect, vi, beforeEach } from 'vitest'

import instructorMiddleware from './instructor'

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

const run = () => (instructorMiddleware as unknown as () => unknown)()

describe('instructor middleware', () => {
  beforeEach(() => {
    mocks.navigateTo.mockClear()
    mocks.hasAnyRole.mockReset()
    mocks.hasAnyRole.mockReturnValue(true)
    mocks.isAuthenticated.value = true
  })

  it('allows instructor and admin users through', () => {
    const result = run()
    expect(result).toBeUndefined()
    expect(mocks.navigateTo).not.toHaveBeenCalled()
    expect(mocks.hasAnyRole).toHaveBeenCalledWith([
      'instructor',
      'org-admin',
      'platform-admin',
    ])
  })

  it('redirects unauthenticated users to /login with an /instructor redirect', () => {
    mocks.isAuthenticated.value = false
    const result = run()
    expect(mocks.navigateTo).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/instructor' },
    })
    expect(result).toEqual({
      redirectedTo: { path: '/login', query: { redirect: '/instructor' } },
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
