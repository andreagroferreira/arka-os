<script setup lang="ts">
interface KnowledgeStats {
  chunks: number
  files: number
  avg_chunk_size: number
  areas: number
}

interface SearchResult {
  score: number
  source: string
  text: string
  heading?: string
}

const { fetchApi } = useApi()

const { data: stats, pending: statsPending, error: statsError } = await fetchApi<KnowledgeStats>(
  '/api/knowledge/stats',
)

const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const searchPending = ref(false)
const searchError = ref<string | null>(null)
const hasSearched = ref(false)

async function performSearch() {
  if (!searchQuery.value.trim()) return

  searchPending.value = true
  searchError.value = null
  hasSearched.value = true

  try {
    const { data, error: fetchError } = await fetchApi<SearchResult[]>(
      `/api/knowledge/search?q=${encodeURIComponent(searchQuery.value)}`,
    )
    if (fetchError.value) {
      searchError.value = 'Failed to search knowledge base'
    } else {
      searchResults.value = data.value ?? []
    }
  } catch {
    searchError.value = 'Failed to search knowledge base'
  } finally {
    searchPending.value = false
  }
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'text-green-400'
  if (score >= 0.5) return 'text-yellow-400'
  return 'text-gray-400'
}

function truncateText(text: string, maxLength = 200): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-white mb-6">
      Knowledge Base
    </h2>

    <!-- Stats -->
    <div v-if="statsPending" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <UCard v-for="i in 4" :key="i">
        <div class="animate-pulse space-y-2">
          <div class="h-3 bg-gray-700 rounded w-16" />
          <div class="h-6 bg-gray-700 rounded w-12" />
        </div>
      </UCard>
    </div>

    <div v-else-if="statsError" class="mb-8">
      <UCard>
        <p role="alert" class="text-red-400 text-sm">
          Failed to load knowledge base stats.
        </p>
      </UCard>
    </div>

    <div v-else-if="stats" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <StatsCard title="Chunks" :value="stats.chunks.toLocaleString()" color="info" />
      <StatsCard title="Files" :value="stats.files" color="neutral" />
      <StatsCard title="Avg Chunk Size" :value="`${stats.avg_chunk_size} tokens`" color="neutral" />
      <StatsCard title="Knowledge Areas" :value="stats.areas" color="primary" />
    </div>

    <!-- Search -->
    <UCard class="mb-6">
      <form class="flex gap-3" @submit.prevent="performSearch">
        <UInput
          v-model="searchQuery"
          placeholder="Search the knowledge base..."
          class="flex-1"
          aria-label="Search knowledge base"
        />
        <UButton
          type="submit"
          color="primary"
          :loading="searchPending"
          :disabled="!searchQuery.trim()"
        >
          Search
        </UButton>
      </form>
    </UCard>

    <!-- Search results -->
    <div v-if="searchPending" class="space-y-3">
      <UCard v-for="i in 3" :key="i">
        <div class="animate-pulse space-y-2">
          <div class="h-4 bg-gray-700 rounded w-48" />
          <div class="h-3 bg-gray-700 rounded w-full" />
          <div class="h-3 bg-gray-700 rounded w-3/4" />
        </div>
      </UCard>
    </div>

    <div v-else-if="searchError" role="alert">
      <UCard>
        <p class="text-red-400 text-sm">{{ searchError }}</p>
      </UCard>
    </div>

    <div v-else-if="hasSearched && !searchResults.length" class="text-center py-12">
      <p class="text-gray-500">
        No results found for "{{ searchQuery }}".
      </p>
    </div>

    <div v-else-if="searchResults.length" class="space-y-3">
      <p class="text-sm text-gray-500 mb-2">
        {{ searchResults.length }} result{{ searchResults.length !== 1 ? 's' : '' }}
      </p>

      <UCard v-for="(result, idx) in searchResults" :key="idx">
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <h3 v-if="result.heading" class="text-sm font-semibold text-white">
                {{ result.heading }}
              </h3>
              <span class="text-xs text-gray-600 font-mono">{{ result.source }}</span>
            </div>
            <span class="text-xs font-mono" :class="scoreColor(result.score)">
              {{ (result.score * 100).toFixed(0) }}%
            </span>
          </div>
          <p class="text-sm text-gray-400 leading-relaxed">
            {{ truncateText(result.text) }}
          </p>
        </div>
      </UCard>
    </div>
  </div>
</template>
