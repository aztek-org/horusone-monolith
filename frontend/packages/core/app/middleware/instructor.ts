/**
 * Instructor middleware — restricts access to instructor and org-admin roles.
 * Apply to instructor pages with: definePageMeta({ middleware: ['auth', 'instructor'] })
 */
export default defineNuxtRouteMiddleware(() => {
  if (import.meta.server) return

  const { isAuthenticated, hasAnyRole } = useAuth()

  if (!isAuthenticated.value) {
    return navigateTo({
      path: '/login',
      query: { redirect: '/instructor' },
    })
  }

  if (!hasAnyRole('instructor', 'org-admin', 'platform-admin')) {
    return navigateTo({
      path: '/dashboard',
      query: { error: 'insufficient-permissions' },
    })
  }
})
