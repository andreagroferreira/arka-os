<script setup lang="ts">
withDefaults(defineProps<{
  live?: boolean
  interactive?: boolean
  as?: string
  padded?: boolean
}>(), {
  live: false,
  interactive: false,
  as: 'div',
  padded: true
})
</script>

<template>
  <component
    :is="as"
    class="arka-glow-card"
    :class="padded ? 'p-4 sm:p-5' : ''"
    :data-live="live || undefined"
    :data-interactive="interactive || undefined"
  >
    <slot />
  </component>
</template>
