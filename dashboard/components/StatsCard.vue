<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  subtitle?: string
  color?: 'primary' | 'success' | 'warning' | 'error' | 'info' | 'neutral'
}>()
</script>

<template>
  <UCard>
    <div class="flex flex-col gap-1">
      <p class="text-sm font-medium text-gray-400">
        {{ title }}
      </p>
      <p
        class="text-3xl font-bold tracking-tight"
        :class="{
          'text-primary-400': color === 'primary' || !color,
          'text-green-400': color === 'success',
          'text-yellow-400': color === 'warning',
          'text-red-400': color === 'error',
          'text-blue-400': color === 'info',
          'text-gray-200': color === 'neutral',
        }"
      >
        {{ value }}
      </p>
      <p v-if="subtitle" class="text-xs text-gray-500">
        {{ subtitle }}
      </p>
    </div>
  </UCard>
</template>
