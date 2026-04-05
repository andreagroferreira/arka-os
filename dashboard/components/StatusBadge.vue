<script setup lang="ts">
const props = defineProps<{
  status: string
}>()

const colorMap: Record<string, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  HEALTHY: 'success',
  MODERATE: 'warning',
  APPROVAL_REQUIRED: 'error',
  EXCEEDED: 'error',
  completed: 'success',
  processing: 'info',
  queued: 'neutral',
  failed: 'error',
  pass: 'success',
  fail: 'error',
}

const badgeColor = computed(() => colorMap[props.status] ?? 'neutral')
</script>

<template>
  <UBadge :color="badgeColor" variant="subtle" size="sm">
    {{ status }}
  </UBadge>
</template>
