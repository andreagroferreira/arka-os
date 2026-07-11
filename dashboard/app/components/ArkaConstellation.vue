<script setup lang="ts">
// Canvas particle field: 86 agents clustered around 17 department hubs.
// Breathing amplitude scales with the department's calls_30d. Hover finds
// the nearest node (tooltip); click navigates. rAF pauses when the tab is
// hidden; prefers-reduced-motion renders one static frame.
import { useDocumentVisibility, useElementSize } from '@vueuse/core'

interface AgentNode {
  id: string
  name: string
  department: string
  tier: number
}
interface DeptMeta {
  department: string
  calls_30d: number
}

const props = withDefaults(defineProps<{
  agents: AgentNode[]
  departments: DeptMeta[]
  height?: number
}>(), {
  height: 380
})

const router = useRouter()
const wrap = ref<HTMLElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const { width } = useElementSize(wrap)
const visibility = useDocumentVisibility()

const hovered = ref<{ x: number, y: number, name: string, department: string } | null>(null)

interface Star {
  agent: AgentNode
  cx: number
  cy: number
  baseR: number
  phase: number
  speed: number
  intensity: number
  x: number
  y: number
}

let stars: Star[] = []
let hubs: Record<string, { x: number, y: number }> = {}
let frame = 0
let time = 0

function primaryColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--ui-primary').trim() || '#00FF88'
}
function mutedColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--ui-text-muted').trim() || '#8A958F'
}

function layout() {
  const w = width.value || 800
  const h = props.height
  const depts = [...new Set(props.agents.map(a => a.department))].sort()
  const maxCalls = Math.max(1, ...props.departments.map(d => d.calls_30d))
  const callsByDept = Object.fromEntries(props.departments.map(d => [d.department, d.calls_30d]))

  hubs = {}
  depts.forEach((dept, i) => {
    // Golden-angle spiral keeps 17 hubs evenly spread at any aspect ratio.
    const angle = i * 2.399963
    const radius = 0.16 + 0.34 * Math.sqrt((i + 0.5) / depts.length)
    hubs[dept] = {
      x: w / 2 + Math.cos(angle) * radius * w * 0.9,
      y: h / 2 + Math.sin(angle) * radius * h * 0.85
    }
  })

  stars = props.agents.map((agent, i) => {
    const hub = hubs[agent.department] ?? { x: w / 2, y: h / 2 }
    const angle = (i * 2.399963) % (Math.PI * 2)
    const spread = 18 + (i % 5) * 9
    const intensity = (callsByDept[agent.department] ?? 0) / maxCalls
    return {
      agent,
      cx: hub.x + Math.cos(angle) * spread,
      cy: hub.y + Math.sin(angle) * spread * 0.7,
      baseR: agent.tier === 0 ? 3.2 : agent.tier === 1 ? 2.6 : 2,
      phase: Math.random() * Math.PI * 2,
      speed: 0.4 + Math.random() * 0.5,
      intensity,
      x: 0,
      y: 0
    }
  })
}

function draw(animate: boolean) {
  const el = canvas.value
  if (!el) return
  const ctx = el.getContext('2d')
  if (!ctx) return
  const w = width.value || 800
  const h = props.height
  const dpr = window.devicePixelRatio || 1
  if (el.width !== w * dpr || el.height !== h * dpr) {
    el.width = w * dpr
    el.height = h * dpr
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)

  const green = primaryColor()
  const gray = mutedColor()

  // Faint links: agent → its department hub.
  ctx.lineWidth = 0.5
  for (const s of stars) {
    const hub = hubs[s.agent.department]
    if (!hub) continue
    const drift = animate ? Math.sin(time * s.speed + s.phase) * (2 + s.intensity * 4) : 0
    s.x = s.cx + drift
    s.y = s.cy + Math.cos(time * s.speed * 0.8 + s.phase) * (animate ? 2 + s.intensity * 3 : 0)
    ctx.strokeStyle = `color-mix(in srgb, ${gray} 12%, transparent)`
    ctx.beginPath()
    ctx.moveTo(hub.x, hub.y)
    ctx.lineTo(s.x, s.y)
    ctx.stroke()
  }

  // Stars: breathing radius + glow proportional to activity.
  for (const s of stars) {
    const breath = animate ? (Math.sin(time * 1.4 * s.speed + s.phase) + 1) / 2 : 0.5
    const r = s.baseR + breath * (0.6 + s.intensity * 1.6)
    const alpha = 0.45 + s.intensity * 0.4 + breath * 0.15
    ctx.beginPath()
    ctx.arc(s.x, s.y, r, 0, Math.PI * 2)
    ctx.fillStyle = `color-mix(in srgb, ${green} ${Math.round(alpha * 100)}%, transparent)`
    ctx.shadowColor = s.intensity > 0.15 ? green : 'transparent'
    ctx.shadowBlur = s.intensity * 14
    ctx.fill()
    ctx.shadowBlur = 0
  }

  // Hub labels in HUD mono.
  ctx.font = '9px "JetBrains Mono", monospace'
  ctx.fillStyle = `color-mix(in srgb, ${gray} 65%, transparent)`
  ctx.textAlign = 'center'
  for (const [dept, hub] of Object.entries(hubs)) {
    ctx.fillText(dept.toUpperCase(), hub.x, hub.y - 16)
  }
}

function loop() {
  time += 0.016
  draw(true)
  frame = requestAnimationFrame(loop)
}

function start() {
  cancelAnimationFrame(frame)
  layout()
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) {
    draw(false)
    return
  }
  loop()
}

watch([width, () => props.agents, visibility], () => {
  cancelAnimationFrame(frame)
  if (visibility.value !== 'visible') return
  if (props.agents.length) start()
}, { deep: false })

onMounted(() => {
  if (props.agents.length) start()
})
onUnmounted(() => cancelAnimationFrame(frame))

function onMove(e: MouseEvent) {
  const rect = canvas.value?.getBoundingClientRect()
  if (!rect) return
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  let best: Star | null = null
  let bestDist = 18
  for (const s of stars) {
    const d = Math.hypot(s.x - mx, s.y - my)
    if (d < bestDist) {
      best = s
      bestDist = d
    }
  }
  hovered.value = best
    ? { x: best.x, y: best.y, name: best.agent.name, department: best.agent.department }
    : null
}

function onClick() {
  if (hovered.value) router.push('/agents')
}
</script>

<template>
  <div ref="wrap" class="relative w-full" :style="{ height: `${height}px` }">
    <canvas
      ref="canvas"
      class="size-full"
      :class="hovered ? 'cursor-pointer' : ''"
      :style="{ width: '100%', height: `${height}px` }"
      role="img"
      aria-label="Constellation of all agents grouped by department"
      @mousemove="onMove"
      @mouseleave="hovered = null"
      @click="onClick"
    />
    <div
      v-if="hovered"
      class="pointer-events-none absolute z-10 -translate-x-1/2 rounded border border-default bg-elevated px-2 py-1"
      :style="{ left: `${hovered.x}px`, top: `${hovered.y - 34}px` }"
    >
      <span class="text-xs font-medium">{{ hovered.name }}</span>
      <span class="arka-data ml-1.5 text-[10px] text-muted uppercase">{{ hovered.department }}</span>
    </div>
  </div>
</template>
