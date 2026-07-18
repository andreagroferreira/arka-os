<script setup lang="ts">
// PR94c v3.49.0 — minimal side-by-side line diff.
//
// Uses LCS (longest common subsequence) on lines to mark equal / added /
// removed rows. Empty inputs render an italic "—" placeholder. Diff is
// pure client-side — no deps.

const props = defineProps<{
  left: string
  right: string
  leftLabel?: string
  rightLabel?: string
}>()

interface DiffRow {
  kind: 'eq' | 'add' | 'del'
  left: string
  right: string
}

function lineDiff(a: string, b: string): DiffRow[] {
  const left = (a ?? '').split(/\r?\n/)
  const right = (b ?? '').split(/\r?\n/)
  const m = left.length
  const n = right.length
  // Build LCS table.
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
  // Indices below are always in-bounds (loops bounded by lengths; dp has
  // m+1 rows / n+1 cols), so the fallbacks never fire — they only satisfy
  // noUncheckedIndexedAccess. 0 matches the table fill value.
  const cell = (i: number, j: number): number => dp[i]?.[j] ?? 0
  for (let i = m - 1; i >= 0; i -= 1) {
    const row = dp[i]
    if (!row) continue
    for (let j = n - 1; j >= 0; j -= 1) {
      if (left[i] === right[j]) row[j] = cell(i + 1, j + 1) + 1
      else row[j] = Math.max(cell(i + 1, j), cell(i, j + 1))
    }
  }
  // Walk back, emitting rows.
  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    const l = left[i] ?? ''
    const r = right[j] ?? ''
    if (l === r) {
      rows.push({ kind: 'eq', left: l, right: r })
      i += 1
      j += 1
    } else if (cell(i + 1, j) >= cell(i, j + 1)) {
      rows.push({ kind: 'del', left: l, right: '' })
      i += 1
    } else {
      rows.push({ kind: 'add', left: '', right: r })
      j += 1
    }
  }
  while (i < m) {
    rows.push({ kind: 'del', left: left[i] ?? '', right: '' })
    i += 1
  }
  while (j < n) {
    rows.push({ kind: 'add', left: '', right: right[j] ?? '' })
    j += 1
  }
  return rows
}

const rows = computed(() => lineDiff(props.left || '', props.right || ''))

const summary = computed(() => {
  const adds = rows.value.filter(r => r.kind === 'add').length
  const dels = rows.value.filter(r => r.kind === 'del').length
  return { adds, dels }
})
</script>

<template>
  <div class="rounded-lg border border-default overflow-hidden">
    <div class="px-3 py-2 border-b border-default bg-elevated/30 flex items-center justify-between gap-3 text-xs">
      <div class="flex items-center gap-3">
        <span class="font-mono">{{ leftLabel ?? 'left' }}</span>
        <UIcon name="i-lucide-arrow-right" class="size-3 text-muted" />
        <span class="font-mono">{{ rightLabel ?? 'right' }}</span>
      </div>
      <div class="flex items-center gap-2 font-mono text-muted">
        <span v-if="summary.adds > 0" class="text-emerald-500">+{{ summary.adds }}</span>
        <span v-if="summary.dels > 0" class="text-rose-500">-{{ summary.dels }}</span>
        <span v-if="summary.adds === 0 && summary.dels === 0">identical</span>
      </div>
    </div>
    <div class="grid grid-cols-2 text-xs font-mono overflow-x-auto">
      <div>
        <div
          v-for="(row, idx) in rows"
          :key="`l-${idx}`"
          :class="[
            'px-3 py-1 whitespace-pre-wrap break-words border-b border-default/50 min-h-[1.5rem]',
            row.kind === 'del' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' : '',
            row.kind === 'add' ? 'bg-muted/10' : ''
          ]"
        >
          {{ row.left || '·' }}
        </div>
      </div>
      <div class="border-l border-default">
        <div
          v-for="(row, idx) in rows"
          :key="`r-${idx}`"
          :class="[
            'px-3 py-1 whitespace-pre-wrap break-words border-b border-default/50 min-h-[1.5rem]',
            row.kind === 'add' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : '',
            row.kind === 'del' ? 'bg-muted/10' : ''
          ]"
        >
          {{ row.right || '·' }}
        </div>
      </div>
    </div>
  </div>
</template>
