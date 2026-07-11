<script setup lang="ts">
defineProps<{
  numeral: string
  label: string
}>()
</script>

<template>
  <section class="space-y-5">
    <div class="flex items-center gap-3">
      <span class="arka-numeral text-xl leading-none">{{ numeral }}.</span>
      <span class="h-px w-8 bg-[var(--ui-border)]" aria-hidden="true" />
      <span class="arka-eyebrow">{{ label }}</span>
      <div class="ml-auto flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </section>
</template>
