<script setup lang="ts">
// PR64 v2.80.0 — shared loading / error / empty wrapper.
//
// Every page in dashboard/app/pages/ used to duplicate the same triple:
//
//   <div v-if="status === 'pending'"><spinner/></div>
//   <div v-else-if="error"><alert + Retry/></div>
//   <template v-else>... content ...</template>
//
// Five copies of that pattern with subtle drift (different icon sizes,
// different empty-state shapes, inconsistent ARIA roles, some with
// retry buttons missing). PR64 extracts it into one component so the
// rest of the dashboard work (PR63 Settings, PR65 Budget, PR66 Index
// rebuild, etc.) inherits a consistent shell.
//
// Slots:
//   default — the success/content block (only rendered on 'success')
//   empty   — optional override for the empty state (defaults to
//             generic "no data" with the empty-* props below)
//   loading — optional override for the spinner (rarely needed)
//   error   — optional override for the error state (rarely needed)
//
// The component never owns the data — pages still call useFetch /
// fetchApi and pass `status` + `error` + an `empty` boolean in.

import type { AsyncDataRequestStatus } from 'nuxt/app'

interface Props {
  /** useFetch/useAsyncData status. 'pending' shows spinner. */
  status: AsyncDataRequestStatus
  /** Error from useFetch — present means render the error block. */
  error?: Error | null
  /** True when the request succeeded but returned no rows.
   *  Pages compute this from their data shape (e.g. `!list.length`). */
  empty?: boolean
  /** Heading for the default empty state. */
  emptyTitle?: string
  /** Helper text for the default empty state. */
  emptyDescription?: string
  /** Icon for the default empty state. Defaults to inbox. */
  emptyIcon?: string
  /** Optional retry handler — when provided, the error block shows a button. */
  onRetry?: () => void | Promise<void>
  /** Optional ARIA label for the loading region. */
  loadingLabel?: string
}

withDefaults(defineProps<Props>(), {
  error: null,
  empty: false,
  emptyTitle: 'No data',
  emptyDescription: '',
  emptyIcon: 'i-lucide-inbox',
  loadingLabel: 'Loading'
})
</script>

<template>
  <!-- Loading -->
  <div
    v-if="status === 'pending'"
    class="flex items-center justify-center py-12"
    :aria-label="loadingLabel"
    role="status"
  >
    <slot name="loading">
      <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
    </slot>
  </div>

  <!-- Error -->
  <div
    v-else-if="error"
    class="flex flex-col items-center justify-center gap-4 py-12"
    role="alert"
  >
    <slot name="error" :error="error">
      <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
      <p class="text-sm text-muted">
        {{ error.message || 'Failed to load data.' }}
      </p>
      <UButton
        v-if="onRetry"
        label="Retry"
        variant="outline"
        color="primary"
        icon="i-lucide-refresh-cw"
        @click="onRetry"
      />
    </slot>
  </div>

  <!-- Empty -->
  <div
    v-else-if="empty"
    class="flex flex-col items-center justify-center gap-4 py-16"
  >
    <slot name="empty">
      <UIcon :name="emptyIcon" class="size-16 text-muted" />
      <h3 class="text-lg font-semibold text-highlighted">
        {{ emptyTitle }}
      </h3>
      <p
        v-if="emptyDescription"
        class="text-sm text-muted text-center max-w-md"
      >
        {{ emptyDescription }}
      </p>
    </slot>
  </div>

  <!-- Content -->
  <slot v-else />
</template>
