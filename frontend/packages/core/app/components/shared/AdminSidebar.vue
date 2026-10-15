<script setup lang="ts">
interface NavItem {
  path: string
  label: string
  icon: string
  exact?: boolean
}

const route = useRoute()

const { hasAnyRole } = useAuth()

const navItems = computed(() => {
  const items: NavItem[] = [
    { path: '/admin', label: 'Overview', icon: 'heroicons:squares-2x2', exact: true },
  ]

  // Organizations/Users are backed by platform-admin-only endpoints, so only
  // platform admins may see those links (org-admins would get a 403).
  if (hasAnyRole('platform-admin')) {
    items.push(
      { path: '/admin/organizations', label: 'Organizations', icon: 'heroicons:building-office-2' },
      { path: '/admin/users', label: 'Users', icon: 'heroicons:users' },
    )
  }

  items.push(
    { path: '/admin/modules', label: 'Modules', icon: 'heroicons:academic-cap' },
    { path: '/admin/leaderboard', label: 'Leaderboard', icon: 'heroicons:trophy' },
  )

  // Add Instructor link for instructor/org-admin roles
  if (hasAnyRole('instructor', 'org-admin')) {
    items.push({ path: '/instructor', label: 'Instructor', icon: 'heroicons:academic-cap' })
  }

  return items
})

function isActive(item: NavItem): boolean {
  if (item.exact) {
    return route.path === item.path
  }
  return route.path.startsWith(item.path)
}
</script>

<template>
  <aside class="w-60 flex-shrink-0 border-r border-horus-border-subtle bg-horus-bg-secondary/50 overflow-y-auto">
    <div class="p-4 space-y-6">
      <!-- Header -->
      <div class="px-2">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded-lg bg-horus-accent-cyan/20 flex items-center justify-center">
            <Icon
              name="heroicons:shield-check"
              class="w-4 h-4 text-horus-accent-cyan"
            />
          </div>
          <div>
            <h2 class="text-sm font-semibold text-horus-text-primary">
              Admin Panel
            </h2>
            <p class="text-xxs text-horus-text-muted uppercase tracking-wider">
              Platform Management
            </p>
          </div>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="space-y-1">
        <NuxtLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
            isActive(item)
              ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border border-horus-accent-cyan/20'
              : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary border border-transparent',
          ]"
        >
          <Icon
            :name="item.icon"
            :class="[
              'w-5 h-5 flex-shrink-0',
              isActive(item) ? 'text-horus-accent-cyan' : 'text-horus-text-muted',
            ]"
          />
          {{ item.label }}
        </NuxtLink>
      </nav>

      <!-- Divider -->
      <div class="border-t border-horus-border-subtle" />

      <!-- Back Link -->
      <NuxtLink
        to="/dashboard"
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
      >
        <Icon
          name="heroicons:arrow-left"
          class="w-5 h-5 flex-shrink-0"
        />
        Back to App
      </NuxtLink>
    </div>
  </aside>
</template>
