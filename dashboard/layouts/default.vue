<script setup lang="ts">
const route = useRoute()

interface NavItem {
  label: string
  to: string
  badge?: string
}

const navItems: NavItem[] = [
  { label: 'Overview', to: '/' },
  { label: 'Agents', to: '/agents' },
  { label: 'Commands', to: '/commands' },
  { label: 'Budget', to: '/budget' },
  { label: 'Tasks', to: '/tasks' },
  { label: 'Knowledge', to: '/knowledge' },
  { label: 'Health', to: '/health' },
]

const sidebarOpen = ref(true)

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

function isActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}
</script>

<template>
  <div class="flex h-screen bg-gray-950 text-gray-100">
    <!-- Mobile sidebar toggle -->
    <button
      class="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-md bg-gray-800 hover:bg-gray-700"
      aria-label="Toggle sidebar navigation"
      @click="toggleSidebar"
    >
      <span class="text-sm">Menu</span>
    </button>

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-40 w-64 bg-gray-900 border-r border-gray-800 flex flex-col transition-transform duration-200 lg:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
      role="navigation"
      aria-label="Main navigation"
    >
      <!-- Header -->
      <div class="flex items-center gap-3 px-6 py-5 border-b border-gray-800">
        <h1 class="text-lg font-bold text-white tracking-tight">
          ArkaOS
        </h1>
        <UBadge color="primary" variant="subtle" size="sm">
          v2.0.0
        </UBadge>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <NuxtLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
          :class="
            isActive(item.to)
              ? 'bg-primary-500/10 text-primary-400'
              : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
          "
          :aria-current="isActive(item.to) ? 'page' : undefined"
          @click="sidebarOpen = false"
        >
          {{ item.label }}
        </NuxtLink>
      </nav>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-gray-800">
        <p class="text-xs text-gray-600">
          ArkaOS Dashboard
        </p>
        <p class="text-xs text-gray-700">
          56 agents / 16 departments
        </p>
      </div>
    </aside>

    <!-- Overlay for mobile -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-30 bg-black/50 lg:hidden"
      @click="sidebarOpen = false"
    />

    <!-- Main content -->
    <main class="flex-1 lg:ml-64 overflow-y-auto">
      <div class="max-w-7xl mx-auto px-6 py-8">
        <slot />
      </div>
    </main>
  </div>
</template>
