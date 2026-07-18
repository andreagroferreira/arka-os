<script setup lang="ts">
// PR85d v3.14.0 — global search command palette.
//
// Opens via `/` shortcut. Debounced fetch against /api/search hits
// agents, personas, departments, commands. Navigate by Enter or click.

const { searchOpen } = useDashboard()
const { apiBase } = useApi()
const router = useRouter()

interface SearchResult {
  kind: 'agent' | 'persona' | 'department' | 'command'
  id: string
  label: string
  sublabel: string
  to: string
}

const query = ref('')
const results = ref<SearchResult[]>([])
const loading = ref(false)
let abortCtl: AbortController | null = null
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(query, (q) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (abortCtl) abortCtl.abort()
  if (!q.trim()) {
    results.value = []
    loading.value = false
    return
  }
  debounceTimer = setTimeout(async () => {
    loading.value = true
    abortCtl = new AbortController()
    try {
      const res = await $fetch<{ results: SearchResult[] }>(
        `${apiBase}/api/search`,
        { query: { q, limit: 20 }, signal: abortCtl.signal }
      )
      results.value = res.results ?? []
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 180)
})

watch(searchOpen, (open) => {
  if (!open) {
    query.value = ''
    results.value = []
  }
})

function pickResult(r: SearchResult) {
  searchOpen.value = false
  router.push(r.to)
}

const kindMeta: Record<SearchResult['kind'], { icon: string, color: string }> = {
  agent: { icon: 'i-lucide-users', color: 'text-primary' },
  persona: { icon: 'i-lucide-user-plus', color: 'text-emerald-500' },
  department: { icon: 'i-lucide-folder-tree', color: 'text-amber-500' },
  command: { icon: 'i-lucide-terminal', color: 'text-blue-500' }
}
</script>

<template>
  <UModal
    v-model:open="searchOpen"
    title="Search"
    :ui="{ content: 'max-w-2xl' }"
  >
    <template #content>
      <UCard :ui="{ body: 'p-0' }">
        <template #header>
          <div class="flex items-center gap-3">
            <UIcon name="i-lucide-search" class="size-5 text-muted shrink-0" />
            <UInput
              v-model="query"
              placeholder="Search agents, personas, departments, commands…"
              size="lg"
              autofocus
              :ui="{ root: 'flex-1', base: 'border-0 shadow-none ring-0 focus:ring-0 px-0' }"
            />
            <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 text-xs font-mono text-muted shrink-0">
              esc
            </kbd>
          </div>
        </template>

        <div class="max-h-[60vh] overflow-y-auto">
          <div v-if="loading" class="p-6 text-center text-sm text-muted">
            <UIcon name="i-lucide-loader-2" class="size-4 animate-spin inline" />
            Searching…
          </div>
          <div
            v-else-if="!query.trim()"
            class="p-6 text-center text-sm text-muted"
          >
            Start typing to search across the whole workspace.
          </div>
          <div
            v-else-if="results.length === 0"
            class="p-6 text-center text-sm text-muted"
          >
            No matches for <span class="font-mono">{{ query }}</span>.
          </div>
          <ul v-else class="divide-y divide-default">
            <li
              v-for="r in results"
              :key="`${r.kind}:${r.id}`"
              class="px-4 py-2.5 hover:bg-elevated/40 cursor-pointer transition-colors"
              @click="pickResult(r)"
            >
              <div class="flex items-center gap-3">
                <UIcon
                  :name="kindMeta[r.kind].icon"
                  class="size-4 shrink-0"
                  :class="kindMeta[r.kind].color"
                />
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-semibold truncate">
                    {{ r.label }}
                  </p>
                  <p class="text-xs text-muted truncate">
                    {{ r.sublabel }}
                  </p>
                </div>
                <UBadge
                  :label="r.kind"
                  variant="subtle"
                  size="xs"
                  class="capitalize shrink-0"
                />
              </div>
            </li>
          </ul>
        </div>

        <template #footer>
          <div class="text-xs text-muted flex items-center gap-3">
            <span>
              <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 font-mono">/</kbd>
              opens this
            </span>
            <span>
              <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 font-mono">esc</kbd>
              closes
            </span>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
