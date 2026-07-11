<script setup lang="ts">
import { useTimestamp } from '@vueuse/core'

withDefaults(defineProps<{
  numeral: string
  label: string
  title: string
  subtitle?: string
  clock?: boolean
}>(), {
  subtitle: '',
  clock: true
})

const timestamp = useTimestamp({ interval: 1000 })
const clockLabel = computed(() =>
  new Date(timestamp.value).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
)
</script>

<template>
  <header class="space-y-3">
    <div class="flex items-center gap-3">
      <span class="arka-numeral text-2xl leading-none">{{ numeral }}.</span>
      <span class="h-px w-10 bg-[var(--ui-border)]" aria-hidden="true" />
      <span class="arka-eyebrow">{{ label }}</span>
      <div class="ml-auto flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <h1 class="arka-serif-title text-4xl sm:text-5xl">
      {{ title }}
    </h1>
    <p v-if="subtitle" class="max-w-2xl text-muted">
      {{ subtitle }}
    </p>
    <p v-if="clock" class="arka-data text-xs text-muted uppercase tracking-wide">
      {{ clockLabel }} · local · studio
    </p>
    <slot name="stats" />
  </header>
</template>
