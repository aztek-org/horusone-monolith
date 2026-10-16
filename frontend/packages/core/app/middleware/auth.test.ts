import { describe, it, expect, vi, beforeEach } from 'vitest'

import authMiddleware from './auth'

const mocks = vi.hoisted(() => ({
  isAuthenticated: { value: true },
  isLoading: { value: false },
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
    isLoading: mocks.isLoading,
  }),
}))

const run = (to: { path: string, fullPath: string }) =>
  (authMiddleware as unknown as (to: unknown) => unknown)(to)

describe('auth middleware', () => {
  beforeEach(() => {
    mocks.navigateTo.mockClear()
    mocks.isAuthenticated.value = true
    mocks.isLoading.value = false
  })

  it('allows authenticated users through', () => {
    const result = run({ path: '/dashboard', fullPath: '/dashboard' })
    expect(result).toBeUndefined()
    expect(mocks.navigateTo).not.toHaveBeenCalled()
  })

  it('redirects unauthenticated users to /login with a redirect query', () => {
    mocks.isAuthenticated.value = false
    const result = run({ path: '/dashboard', fullPath: '/dashboard?tab=overview' })
    expect(mocks.navigateTo).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/dashboard?tab=overview' },
    })
    expect(result).toEqual({
      redirectedTo: { path: '/login', query: { redirect: '/dashboard?tab=overview' } },
    })
  })

  it('does not redirect while auth is still loading', () => {
    mocks.isAuthenticated.value = false
    mocks.isLoading.value = true
    const result = run({ path: '/dashboard', fullPath: '/dashboard' })
    expect(result).toBeUndefined()
    expect(mocks.navigateTo).not.toHaveBeenCalled()
  })

  it('skips the public /login route', () => {
    mocks.isAuthenticated.value = false
    const result = run({ path: '/login', fullPath: '/login' })
    expect(result).toBeUndefined()
    expect(mocks.navigateTo).not.toHaveBeenCalled()
  })

  it('skips the public /auth/callback route', () => {
    mocks.isAuthenticated.value = false
    const result = run({ path: '/auth/callback', fullPath: '/auth/callback?code=abc' })
    expect(result).toBeUndefined()
    expect(mocks.navigateTo).not.toHaveBeenCalled()
  })
})
