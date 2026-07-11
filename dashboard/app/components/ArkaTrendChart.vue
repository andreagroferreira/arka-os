<script setup lang="ts">
import { VisXYContainer, VisArea, VisLine, VisAxis } from '@unovis/vue'

interface TrendPoint {
  date: string
  value: number
}

const props = withDefaults(defineProps<{
  series: TrendPoint[]
  height?: number
}>(), {
  height: 160
})

const x = (_: TrendPoint, i: number) => i
const y = (d: TrendPoint) => d.value

const tickValues = computed(() => {
  const n = props.series.length
  if (n <= 7) return props.series.map((_, i) => i)
  const step = Math.ceil(n / 6)
  return props.series.map((_, i) => i).filter(i => i % step === 0)
})

function tickFormat(i: number) {
  const point = props.series[Math.round(i)]
  if (!point) return ''
  return point.date.slice(5)
}
</script>

<template>
  <div class="arka-trend-chart">
    <VisXYContainer :data="series" :height="height">
      <VisArea
        :x="x"
        :y="y"
        color="var(--ui-primary)"
        :opacity="0.12"
        curve-type="monotoneX"
      />
      <VisLine
        :x="x"
        :y="y"
        color="var(--ui-primary)"
        :line-width="1.5"
        curve-type="monotoneX"
      />
      <VisAxis
        type="x"
        :tick-values="tickValues"
        :tick-format="tickFormat"
        :grid-line="false"
        :domain-line="false"
        :tick-line="false"
      />
    </VisXYContainer>
  </div>
</template>

<style scoped>
.arka-trend-chart :deep(text) {
  font-family: var(--font-mono);
  font-size: 10px;
  fill: var(--ui-text-muted);
}
</style>
