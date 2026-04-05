<script setup lang="ts">
import type { KnowledgeStats, KnowledgeSearchResult } from '~/types'

const { fetchApi, apiBase } = useApi()

const { data: stats, status, error, refresh } = await fetchApi<KnowledgeStats>('/api/knowledge/stats')

const isIndexed = computed(() => (stats.value?.total_chunks ?? 0) > 0)

const searchQuery = ref('')
const searchResults = ref<KnowledgeSearchResult[]>([])
const searchTotal = ref(0)
const searching = ref(false)
const hasSearched = ref(false)

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    searchTotal.value = 0
    hasSearched.value = false
    return
  }

  searching.value = true
  hasSearched.value = true
  try {
    const { data } = await useFetch<{ results: KnowledgeSearchResult[], query: string, total: number }>(
      `${apiBase}/api/knowledge/search`,
      { params: { q: searchQuery.value } }
    )
    searchResults.value = data.value?.results ?? []
    searchTotal.value = data.value?.total ?? 0
  } finally {
    searching.value = false
  }
}

function formatScore(score: number): string {
  return `${(score * 100).toFixed(0)}%`
}
</script>

<template>
  <UDashboardPanel id="knowledge">
    <template #header>
      <UDashboardNavbar title="Knowledge Base">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            v-if="stats?.vss_available !== undefined"
            :label="stats.vss_available ? 'VSS Active' : 'VSS Unavailable'"
            :color="stats.vss_available ? 'success' : 'neutral'"
            variant="subtle"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-12" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load knowledge stats.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Stats Section -->
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-highlighted">{{ stats?.total_chunks ?? 0 }}</p>
            <p class="text-xs text-muted">Total Chunks</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-highlighted">{{ stats?.total_files ?? 0 }}</p>
            <p class="text-xs text-muted">Total Files</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <UBadge
              :label="stats?.vss_available ? 'Available' : 'Unavailable'"
              :color="stats?.vss_available ? 'success' : 'neutral'"
              variant="subtle"
              size="sm"
            />
            <p class="text-xs text-muted mt-1">Vector Search</p>
          </div>
        </div>

        <!-- Not Indexed State -->
        <div v-if="!isIndexed" class="mt-8">
          <div class="rounded-lg border-2 border-dashed border-default p-8 text-center">
            <UIcon name="i-lucide-database" class="size-16 text-muted mx-auto" />
            <h3 class="mt-4 text-lg font-semibold text-highlighted">Knowledge base not indexed yet</h3>
            <p class="mt-2 text-sm text-muted max-w-lg mx-auto">
              Index your Obsidian vault to enable semantic search across your entire knowledge base.
            </p>
            <div class="mt-6 inline-block rounded-lg border border-default bg-elevated/50 px-6 py-4 text-left">
              <p class="text-xs text-muted mb-2">Run this command to index:</p>
              <code class="font-mono text-sm text-primary">npx arkaos index</code>
            </div>
            <p class="mt-4 text-xs text-muted max-w-md mx-auto">
              This indexes your markdown files into a local vector database for automatic context retrieval.
              The process runs locally and your data never leaves your machine.
            </p>
          </div>
        </div>

        <!-- Indexed State -->
        <template v-else>
          <!-- Knowledge Areas -->
          <div v-if="stats?.areas?.length" class="mt-6">
            <h3 class="mb-4 text-lg font-semibold text-highlighted">Knowledge Areas</h3>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div
                v-for="area in stats.areas"
                :key="area.name"
                class="rounded-lg border border-default p-4"
              >
                <h4 class="font-medium text-highlighted">{{ area.name }}</h4>
                <div class="mt-2 flex gap-4 text-xs text-muted">
                  <span>{{ area.chunks }} chunks</span>
                  <span>{{ area.files }} files</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Search -->
          <div class="mt-6 rounded-lg border border-default p-6">
            <h3 class="mb-4 text-lg font-semibold text-highlighted">Search Knowledge</h3>
            <form class="flex gap-2" @submit.prevent="handleSearch">
              <UInput
                v-model="searchQuery"
                class="flex-1"
                icon="i-lucide-search"
                placeholder="Search the knowledge base..."
                aria-label="Search knowledge base"
              />
              <UButton
                type="submit"
                label="Search"
                :loading="searching"
                icon="i-lucide-search"
              />
            </form>

            <!-- Search Results -->
            <div v-if="searching" class="mt-4 flex items-center justify-center py-8">
              <UIcon name="i-lucide-loader-2" class="size-6 animate-spin text-muted" />
            </div>

            <template v-else-if="hasSearched">
              <div v-if="searchResults.length" class="mt-4 space-y-3">
                <p class="text-xs text-muted">{{ searchTotal }} result{{ searchTotal !== 1 ? 's' : '' }} found</p>
                <div
                  v-for="(result, idx) in searchResults"
                  :key="result.id ?? idx"
                  class="rounded-lg border border-default p-4"
                >
                  <div class="mb-2 flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2 min-w-0">
                      <UBadge v-if="result.area" :label="result.area" variant="subtle" size="sm" />
                      <span v-if="result.heading" class="text-sm font-medium text-highlighted truncate">
                        {{ result.heading }}
                      </span>
                    </div>
                    <span class="text-xs text-muted whitespace-nowrap">
                      Score: {{ formatScore(result.score) }}
                    </span>
                  </div>
                  <p v-if="result.source" class="text-xs text-muted mb-1 truncate">
                    <UIcon name="i-lucide-file-text" class="size-3 inline-block mr-1" />
                    {{ result.source }}
                  </p>
                  <p class="text-sm text-muted line-clamp-3">
                    {{ result.text || result.content }}
                  </p>
                </div>
              </div>

              <div v-else class="mt-4 text-center text-sm text-muted py-6">
                <UIcon name="i-lucide-search-x" class="size-8 text-muted mx-auto mb-2" />
                <p>No results found for "{{ searchQuery }}".</p>
              </div>
            </template>
          </div>
        </template>
      </template>
    </template>
  </UDashboardPanel>
</template>
