<script setup lang="ts">
// PR86d v3.18.0 — Markdown editor with Edit / Preview tabs.
//
// Standalone component used in agent + persona edit forms. The model
// value is the raw Markdown string. Preview is rendered via marked
// (already a deps after this PR).

import { marked } from 'marked'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  rows?: number
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const tab = ref<'edit' | 'preview'>('edit')

const value = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v)
})

const html = computed(() => {
  if (!value.value.trim()) {
    return '<p class="text-muted italic">Nothing to preview yet.</p>'
  }
  try {
    return marked.parse(value.value, { breaks: true, gfm: true })
  } catch {
    return '<p class="text-error">Markdown parse failed.</p>'
  }
})
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center gap-1 text-xs">
      <button
        type="button"
        class="px-2 py-1 rounded-md transition-colors"
        :class="tab === 'edit' ? 'bg-elevated/60 text-default font-semibold' : 'text-muted hover:text-default'"
        @click="tab = 'edit'"
      >
        Edit
      </button>
      <button
        type="button"
        class="px-2 py-1 rounded-md transition-colors"
        :class="tab === 'preview' ? 'bg-elevated/60 text-default font-semibold' : 'text-muted hover:text-default'"
        @click="tab = 'preview'"
      >
        Preview
      </button>
      <span class="ml-auto text-xs text-muted">
        Markdown · GFM · {{ value.length }} char{{ value.length === 1 ? '' : 's' }}
      </span>
    </div>
    <UTextarea
      v-if="tab === 'edit'"
      v-model="value"
      :rows="rows ?? 8"
      :placeholder="placeholder ?? 'Write a Markdown bio…\n\n# Heading\n- bullets\n**bold**'"
      class="w-full font-mono text-sm"
    />
    <div
      v-else
      class="rounded-lg border border-default bg-elevated/10 p-4 min-h-[12rem] prose prose-sm dark:prose-invert max-w-none"
      v-html="html"
    />
  </div>
</template>
