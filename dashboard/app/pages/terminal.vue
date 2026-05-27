<script setup lang="ts">
// v3.71.0 — the terminal now lives in the app-wide dock (TerminalDock.vue,
// mounted in the default layout). This route simply opens the dock
// maximized, so /terminal stays a valid deep link and the sidebar entry
// keeps working. Leaving the route restores the dock to its docked size
// so it doesn't cover other pages.

import { useTerminalDock } from '~/composables/useTerminalDock'

definePageMeta({ layout: 'default' })

const dock = useTerminalDock()

onMounted(() => dock.open({ maximized: true }))

onBeforeUnmount(() => {
  if (dock.isMaximized.value) dock.toggleMaximize()
})
</script>

<template>
  <UDashboardPanel id="terminal">
    <template #header>
      <UDashboardNavbar title="Terminal">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="h-full grid place-items-center text-center text-muted gap-3 p-8">
        <div>
          <UIcon name="i-lucide-terminal" class="size-10 mx-auto mb-3 opacity-40" />
          <p class="text-sm">
            The terminal runs in the dock — available on every page.
          </p>
          <p class="text-xs mt-1 opacity-70">
            Toggle it anytime with ⌘J. Sessions survive navigation and reload.
          </p>
          <UButton
            class="mt-4"
            icon="i-lucide-terminal"
            @click="dock.open({ maximized: true })"
          >
            Open terminal
          </UButton>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
