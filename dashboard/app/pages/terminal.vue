<script setup lang="ts">
// PR99b v3.68.0 — Real-shell terminal (single session).
//
// Replaces the v3.51.0 allowlist UI. Each visit spawns a fresh PTY
// session on the backend, wired to xterm.js. Multi-session tabs and
// history land in PR99c. The old allowlist endpoints stay in parallel
// until PR99d, but the UI is gone as of this release.

definePageMeta({ layout: 'default' })

const terminalRef = ref<InstanceType<typeof import('~/components/Terminal.vue').default> | null>(null)
const expanded = ref(false)
</script>

<template>
  <div class="flex flex-col gap-3 h-full">
    <header class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Terminal</h1>
        <p class="text-sm text-muted">
          Real shell, PTY-backed. Runs the same commands as your local zsh —
          claude, codex, git, anything. Session ends when you leave this page.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <UBadge color="warning" variant="soft" size="sm">
          <UIcon name="i-lucide-shield" class="size-3 mr-1" />
          localhost only
        </UBadge>
        <UButton
          size="xs"
          variant="ghost"
          :icon="expanded ? 'i-lucide-minimize-2' : 'i-lucide-maximize-2'"
          @click="expanded = !expanded"
        >
          {{ expanded ? 'Restore' : 'Expand' }}
        </UButton>
      </div>
    </header>

    <Terminal
      ref="terminalRef"
      :class="expanded ? 'fixed inset-4 z-40' : 'flex-1 min-h-[520px]'"
    />

    <footer class="text-xs text-muted">
      Multi-session tabs, command history search and theme picker arrive in
      PR99c / PR99d. PR99a (backend PTY) is live.
    </footer>
  </div>
</template>
