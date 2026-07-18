<script setup lang="ts">
// PR85c v3.13.0 — Keyboard shortcuts help overlay.
//
// Triggered by `?` (defineShortcuts in useDashboard). Lists all
// registered shortcuts grouped by category.

const { shortcutsHelpOpen } = useDashboard()

const groups = [
  {
    title: 'Navigation',
    items: [
      { keys: ['g', 'h'], label: 'Home / command center' },
      { keys: ['g', 'a'], label: 'Agents' },
      { keys: ['g', 'p'], label: 'Personas' },
      { keys: ['g', 'c'], label: 'Commands' },
      { keys: ['g', 'b'], label: 'Budget' },
      { keys: ['g', 't'], label: 'Tasks' },
      { keys: ['g', 'k'], label: 'Knowledge' },
      { keys: ['g', 'e'], label: 'Health' },
      { keys: ['g', 'r'], label: 'Trash' },
      { keys: ['g', 's'], label: 'Settings' }
    ]
  },
  {
    title: 'Actions',
    items: [
      { keys: ['/'], label: 'Open global search' },
      { keys: ['n'], label: 'New (context-aware — agent / persona)' },
      { keys: ['?'], label: 'Toggle this help' }
    ]
  }
]
</script>

<template>
  <UModal
    v-model:open="shortcutsHelpOpen"
    title="Keyboard shortcuts"
    :ui="{ content: 'max-w-lg' }"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-bold">
                Keyboard shortcuts
              </h2>
              <p class="text-xs text-muted mt-0.5">
                Press <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 text-xs font-mono">?</kbd> anywhere to toggle this.
              </p>
            </div>
            <UButton
              icon="i-lucide-x"
              variant="ghost"
              size="sm"
              aria-label="Close"
              @click="shortcutsHelpOpen = false"
            />
          </div>
        </template>

        <div class="space-y-5">
          <div v-for="g in groups" :key="g.title">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
              {{ g.title }}
            </h3>
            <ul class="space-y-1.5">
              <li
                v-for="item in g.items"
                :key="item.label"
                class="flex items-center justify-between gap-3 text-sm"
              >
                <span>{{ item.label }}</span>
                <div class="flex items-center gap-1">
                  <kbd
                    v-for="(k, idx) in item.keys"
                    :key="idx"
                    class="px-2 py-0.5 rounded bg-elevated/50 border border-default text-xs font-mono font-semibold"
                  >
                    {{ k }}
                  </kbd>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
