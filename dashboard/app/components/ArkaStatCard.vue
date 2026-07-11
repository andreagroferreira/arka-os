<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  value: number | null
  format?: 'currency' | 'number' | 'percent' | 'tokens'
  decimals?: number
  accent?: boolean
  hint?: string
}>(), {
  format: 'number',
  decimals: 0,
  accent: false,
  hint: ''
})
</script>

<template>
  <ArkaGlowCard :live="accent" class="min-w-0">
    <div class="space-y-2" :class="accent ? 'border-l-2 border-primary -ml-4 pl-4 sm:-ml-5 sm:pl-5' : ''">
      <p class="arka-eyebrow">
        {{ label }}
      </p>
      <p class="text-3xl font-medium leading-none">
        <ArkaCountUp
          v-if="value !== null"
          :value="value"
          :format="format"
          :decimals="decimals"
        />
        <span v-else class="arka-data text-muted">—</span>
      </p>
      <p v-if="hint" class="text-xs text-muted">
        {{ hint }}
      </p>
      <slot name="sparkline" />
    </div>
  </ArkaGlowCard>
</template>
