/**
 * Auth middleware — redirects unauthenticated users to login page.
 * Apply to protected pages with: definePageMeta({ middleware: 'auth' })
 */
export default defineNuxtRouteMiddleware((to) => {
  // Skip on server
  if (import.meta.server) return

  const { isAuthenticated, isLoading } = useAuth()

  // Public routes that don't require auth
  const publicRoutes = ['/login', '/auth/callback']
  if (publicRoutes.some(route => to.path.startsWith(route))) return

  // Wait until auth restoration/callback finishes before deciding redirects.
  if (isLoading.value) return

  if (!isAuthenticated.value) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  }
})
