/**
 * Admin middleware — restricts access to platform-admin and org-admin roles.
 * Apply to admin pages with: definePageMeta({ middleware: ['auth', 'admin'] })
 */
export default defineNuxtRouteMiddleware(() => {
  if (import.meta.server) return

  const { isAuthenticated, hasAnyRole } = useAuth()

  if (!isAuthenticated.value) {
    return navigateTo({
      path: '/login',
      query: { redirect: '/admin' },
    })
  }

  if (!hasAnyRole('platform-admin', 'org-admin')) {
    return navigateTo({
      path: '/dashboard',
      query: { error: 'insufficient-permissions' },
    })
  }
})
