<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

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
  label: 'Tasks',
  icon: 'i-lucide-list-checks',
  to: '/tasks',
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
}], [{
  label: 'Health',
  icon: 'i-lucide-heart-pulse',
  to: '/health',
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
        <div class="flex items-center gap-2" :class="collapsed ? 'justify-center' : ''">
          <span class="text-xl font-bold text-primary">A</span>
          <span v-if="!collapsed" class="font-semibold">ArkaOS</span>
        </div>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :collapsed="collapsed"
          :items="links[0]"
          orientation="vertical"
          tooltip
          popover
        />

        <UNavigationMenu
          :collapsed="collapsed"
          :items="links[1]"
          orientation="vertical"
          tooltip
          class="mt-auto"
        />
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>
