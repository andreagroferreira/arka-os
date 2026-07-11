<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

// PR85c v3.13.0 — registers keyboard shortcuts globally.
useDashboard()

// PR92d v3.42.0 — apply the operator's chosen primary color on boot.
const theme = useThemeColor()
onMounted(() => theme.loadFromStorage())

const open = ref(false)

const links = [[{
  label: 'Overview',
  icon: 'i-lucide-layout-dashboard',
  to: '/',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Agents',
  icon: 'i-lucide-users',
  to: '/agents',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Departments',
  icon: 'i-lucide-folder-tree',
  to: '/departments',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Personas',
  icon: 'i-lucide-user-plus',
  to: '/personas',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Commands',
  icon: 'i-lucide-terminal',
  to: '/commands',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Budget',
  icon: 'i-lucide-wallet',
  to: '/budget',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Models',
  icon: 'i-lucide-layers',
  to: '/models',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Tasks',
  icon: 'i-lucide-list-checks',
  to: '/tasks',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Terminal',
  icon: 'i-lucide-terminal',
  to: '/terminal',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Workflows',
  icon: 'i-lucide-workflow',
  to: '/workflows',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Knowledge',
  icon: 'i-lucide-brain',
  to: '/knowledge',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Dreaming',
  icon: 'i-lucide-sparkles',
  to: '/cognition',
  onSelect: () => {
    open.value = false
  }
}], [{
  label: 'Health',
  icon: 'i-lucide-heart-pulse',
  to: '/health',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Settings',
  icon: 'i-lucide-settings',
  to: '/settings',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Audit',
  icon: 'i-lucide-shield-alert',
  to: '/audit',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Trash',
  icon: 'i-lucide-trash-2',
  to: '/trash',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'GitHub',
  icon: 'i-simple-icons-github',
  to: 'https://github.com/andreagroferreira/arka-os',
  target: '_blank'
}]] satisfies NavigationMenuItem[][]
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="default"
      v-model:open="open"
      collapsible
      resizable
      class="bg-elevated/25"
    >
      <template #header="{ collapsed }">
        <!-- PR72 v2.90.0 — global light/dark switch in the sidebar
             header. Nuxt UI's canonical UColorModeButton (per
             /websites/ui_nuxt docs) flips between sun/moon icons and
             handles SSR via ClientOnly internally. Visible on every
             page; the Settings → Theme section keeps the explicit
             3-way picker (system / light / dark). -->
        <div
          class="flex items-center w-full"
          :class="collapsed ? 'justify-center' : 'justify-between gap-2'"
        >
          <div class="flex items-baseline gap-2">
            <span class="text-xl font-bold text-primary">A</span>
            <span v-if="!collapsed" class="text-lg">
              <span class="font-semibold">Arka</span><span class="arka-serif-accent text-primary">OS</span>
            </span>
          </div>
          <div v-if="!collapsed" class="flex items-center gap-1">
            <NotificationsBell />
            <UColorModeButton size="xs" />
          </div>
        </div>
      </template>

      <template #default="{ collapsed }">
        <ArkaNavGroupLabel v-if="!collapsed" label="workspace" />
        <UNavigationMenu
          :collapsed="collapsed"
          :items="links[0]"
          orientation="vertical"
          tooltip
          popover
        />

        <!-- PR98b v3.64.0 — favorites quick list -->
        <SidebarFavoritesWidget v-if="!collapsed" class="mt-auto" />

        <!-- PR87d v3.22.0 — quick stats widget above the bottom nav. -->
        <SidebarStatsWidget v-if="!collapsed" />

        <ArkaNavGroupLabel v-if="!collapsed" label="system" />
        <UNavigationMenu
          :collapsed="collapsed"
          :items="links[1]"
          orientation="vertical"
          tooltip
          :class="collapsed ? 'mt-auto' : ''"
        />
      </template>

      <template #footer="{ collapsed }">
        <ArkaSystemPill v-if="!collapsed" class="w-full justify-center" />
      </template>
    </UDashboardSidebar>

    <ArkaStarfield />
    <slot />
    <KeyboardShortcutsHelp />
    <GlobalSearch />
    <OnboardingTour />
    <!-- v3.71.0 — app-wide terminal dock. Mounted once here (outside
         <NuxtPage>) so PTY sessions survive route navigation. Client-only
         because xterm.js + WebSocket have no SSR. -->
    <ClientOnly>
      <TerminalDock />
    </ClientOnly>
  </UDashboardGroup>
</template>
