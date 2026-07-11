<script setup lang="ts">
const props = withDefaults(defineProps<{
  value: number
  format?: 'currency' | 'number' | 'percent' | 'tokens'
  decimals?: number
  duration?: number
}>(), {
  format: 'number',
  decimals: 0,
  duration: 900
})

const target = computed(() => props.value ?? 0)
const { display } = useCountUp(target, props.duration)

const formatted = computed(() => {
  const v = display.value
  if (props.format === 'currency') {
    return `$${v.toFixed(Math.max(props.decimals, 2))}`
  }
  if (props.format === 'percent') {
    return `${(v * 100).toFixed(props.decimals)}%`
  }
  if (props.format === 'tokens') {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`
    return Math.round(v).toString()
  }
  return Math.round(v).toLocaleString('en-US')
})
</script>

<template>
  <span class="arka-data">{{ formatted }}</span>
</template>
