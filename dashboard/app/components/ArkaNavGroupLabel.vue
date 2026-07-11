<script setup lang="ts">
defineProps<{
  label: string
}>()
</script>

<template>
  <p class="arka-eyebrow px-2.5 pt-4 pb-1 text-[10px]">
    {{ label }}
  </p>
</template>
