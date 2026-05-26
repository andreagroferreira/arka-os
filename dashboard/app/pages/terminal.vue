<script setup lang="ts">
// PR95a v3.51.0 — Dashboard terminal (allowlist mode).
//
// Operator picks one of the allowlisted commands; backend runs it via
// subprocess.run (no shell). Output streams into the history block.
//
// Note: vue-termui is for building Vue TUI apps that RUN in a terminal,
// not for embedding an arbitrary shell in a browser. The dashboard
// instead ships a controlled command runner with allowlist + capped
// output. xterm.js-style PTY can be a later upgrade if needed.

interface CommandEntry {
  id: string
  label: string
  description: string
}

interface ExecResult {
  stdout: string
  stderr: string
  exit_code: number
  duration_ms: number
  command: string
}

interface HistoryEntry {
  id: string
  label: string
  result: ExecResult
  ts: string
}

const { fetchApi, apiBase } = useApi()
const toast = useToast()

const { data: cmdData, status } = await fetchApi<{ commands: CommandEntry[] }>(
  '/api/terminal/commands',
)
const commands = computed<CommandEntry[]>(() => cmdData.value?.commands ?? [])

const running = ref<string | null>(null)
const history = ref<HistoryEntry[]>([])

async function run(cmd: CommandEntry) {
  running.value = cmd.id
  try {
    const res = await $fetch<ExecResult & { error?: string }>(
      `${apiBase}/api/terminal/exec`,
      { method: 'POST', body: { command_id: cmd.id } },
    )
    if (res.error) throw new Error(res.error)
    history.value = [
      {
        id: cmd.id,
        label: cmd.label,
        result: res,
        ts: new Date().toISOString(),
      },
      ...history.value,
    ].slice(0, 20)
    if (res.exit_code === 0) {
      toast.add({
        title: `${cmd.label} · ok`,
        description: `${res.duration_ms}ms`,
        color: 'success',
        icon: 'i-lucide-check',
      })
    } else {
      toast.add({
        title: `${cmd.label} · exit ${res.exit_code}`,
        description: `${res.duration_ms}ms · ${res.stderr.slice(0, 80) || 'no stderr'}`,
        color: 'warning',
      })
    }
  } catch (err) {
    toast.add({
      title: 'Run failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    running.value = null
  }
}

function copyOutput(entry: HistoryEntry) {
  if (typeof navigator === 'undefined' || !navigator.clipboard) return
  const body = entry.result.stdout || entry.result.stderr
  void navigator.clipboard.writeText(body)
  toast.add({ title: 'Copied to clipboard', color: 'success', icon: 'i-lucide-clipboard-check' })
}

function clearHistory() {
  history.value = []
}

function relative(iso: string): string {
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return iso
  const diff = Date.now() - ts
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
}
</script>

<template>
  <UDashboardPanel id="terminal">
    <template #header>
      <UDashboardNavbar title="Terminal">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge label="Allowlist mode" variant="subtle" color="primary" size="sm" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :empty="commands.length === 0"
        empty-title="No allowlisted commands"
        empty-description="The backend exposes no terminal commands. Add to TERMINAL_ALLOWLIST."
        empty-icon="i-lucide-terminal"
      >
        <div class="space-y-5 max-w-4xl">
          <UCard>
            <template #header>
              <div>
                <h3 class="text-lg font-bold">Commands</h3>
                <p class="text-xs text-muted mt-0.5">
                  Server-enforced allowlist. Each command runs via
                  <code class="font-mono">subprocess.run</code> with explicit argv —
                  no shell, no globbing, no pipes. Cap: 15s timeout, 20K chars per stream.
                </p>
              </div>
            </template>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
              <UButton
                v-for="cmd in commands"
                :key="cmd.id"
                :label="cmd.label"
                :description="cmd.description"
                icon="i-lucide-terminal"
                variant="soft"
                color="primary"
                size="sm"
                block
                class="justify-start"
                :loading="running === cmd.id"
                :disabled="running !== null && running !== cmd.id"
                @click="run(cmd)"
              />
            </div>
          </UCard>

          <UCard v-if="history.length > 0">
            <template #header>
              <div class="flex items-center justify-between gap-3">
                <div>
                  <h3 class="text-lg font-bold">Recent runs</h3>
                  <p class="text-xs text-muted mt-0.5">
                    Last {{ history.length }} commands · most recent first
                  </p>
                </div>
                <UButton label="Clear" variant="ghost" size="xs" @click="clearHistory" />
              </div>
            </template>
            <ul class="space-y-4">
              <li
                v-for="entry in history"
                :key="`${entry.ts}-${entry.id}`"
                class="rounded-lg border border-default overflow-hidden"
              >
                <div class="px-3 py-2 bg-elevated/30 flex items-center justify-between gap-3 text-xs">
                  <div class="min-w-0 flex items-center gap-2">
                    <UBadge
                      :label="entry.result.exit_code === 0 ? 'ok' : `exit ${entry.result.exit_code}`"
                      :color="entry.result.exit_code === 0 ? 'success' : 'warning'"
                      variant="subtle"
                      size="xs"
                    />
                    <span class="font-mono truncate">{{ entry.result.command }}</span>
                  </div>
                  <div class="flex items-center gap-2 shrink-0">
                    <span class="text-muted font-mono">{{ entry.result.duration_ms }}ms</span>
                    <span class="text-muted">{{ relative(entry.ts) }}</span>
                    <UButton
                      icon="i-lucide-clipboard-copy"
                      variant="ghost"
                      size="xs"
                      aria-label="Copy output"
                      @click="copyOutput(entry)"
                    />
                  </div>
                </div>
                <pre
                  v-if="entry.result.stdout"
                  class="p-3 text-xs font-mono whitespace-pre overflow-x-auto"
                >{{ entry.result.stdout }}</pre>
                <pre
                  v-if="entry.result.stderr"
                  class="p-3 text-xs font-mono whitespace-pre overflow-x-auto text-rose-500 border-t border-default"
                >{{ entry.result.stderr }}</pre>
              </li>
            </ul>
          </UCard>

          <p class="text-xs text-muted">
            Want a different command? Add it to
            <code class="font-mono">TERMINAL_ALLOWLIST</code> in
            <code class="font-mono">scripts/dashboard-api.py</code> and
            restart the backend. Arbitrary shell execution from the
            dashboard is intentionally not supported.
          </p>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
