<script setup lang="ts">
// PR98d v3.66.0 — Agent dependency graph.
//
// Shows the current agent in the middle, its linked personas above,
// and other agents that link to those same personas (siblings) below.
// Pure SVG, no graph lib. Frontend-only — reuses existing endpoints.

interface Props {
  agentId: string
  agentName: string
  linkedPersonas: string[]
}
const props = defineProps<Props>()

const { fetchApi } = useApi()

// /api/personas/usage returns the reverse lookup we need.
const { data: usageData } = fetchApi<{
  by_persona: Record<string, { agent_count: number, agent_ids: string[] }>
}>('/api/personas/usage')

// /api/personas for resolving persona names.
const { data: personasData } = fetchApi<{
  personas: Array<{ id: string, name: string }>
}>('/api/personas')

function personaName(id: string): string {
  return personasData.value?.personas?.find((p) => p.id === id)?.name ?? id
}

const siblings = computed<string[]>(() => {
  const ids = new Set<string>()
  const usage = usageData.value?.by_persona ?? {}
  for (const pid of props.linkedPersonas) {
    for (const aid of (usage[pid]?.agent_ids ?? [])) {
      if (aid && aid !== props.agentId) ids.add(aid)
    }
  }
  return Array.from(ids).slice(0, 6)
})

// Layout constants — keep tight so the graph fits the hero card.
const WIDTH = 700
const HEIGHT = 220
const CENTER_X = WIDTH / 2
const CENTER_Y = HEIGHT / 2
const NODE_W = 110
const NODE_H = 32
const NODE_RX = 8

function distributeX(count: number, idx: number): number {
  if (count === 1) return CENTER_X
  const span = Math.min(WIDTH - 80, count * (NODE_W + 20))
  const start = (WIDTH - span) / 2 + NODE_W / 2
  const step = count > 1 ? (span - NODE_W) / (count - 1) : 0
  return start + idx * step
}

const personaPositions = computed(() =>
  props.linkedPersonas.map((id, i) => ({
    id,
    x: distributeX(props.linkedPersonas.length, i),
    y: 32,
  })),
)
const siblingPositions = computed(() =>
  siblings.value.map((id, i) => ({
    id,
    x: distributeX(siblings.value.length, i),
    y: HEIGHT - 32,
  })),
)
</script>

<template>
  <div
    v-if="props.linkedPersonas.length > 0 || siblings.length > 0"
    class="rounded-xl border border-default bg-elevated/10 p-5"
  >
    <h3 class="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
      Dependency graph
    </h3>
    <svg
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      class="w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <!-- Connector lines (personas → center) -->
      <line
        v-for="p in personaPositions"
        :key="`pl-${p.id}`"
        :x1="p.x"
        :y1="p.y + NODE_H / 2"
        :x2="CENTER_X"
        :y2="CENTER_Y - NODE_H / 2"
        class="stroke-default"
        stroke-width="1"
      />
      <!-- Connector lines (center → siblings) -->
      <line
        v-for="s in siblingPositions"
        :key="`sl-${s.id}`"
        :x1="CENTER_X"
        :y1="CENTER_Y + NODE_H / 2"
        :x2="s.x"
        :y2="s.y - NODE_H / 2"
        class="stroke-default"
        stroke-width="1"
        stroke-dasharray="3,2"
      />

      <!-- Persona nodes (top) -->
      <g
        v-for="p in personaPositions"
        :key="`p-${p.id}`"
      >
        <a :href="`/personas/${p.id}`">
          <rect
            :x="p.x - NODE_W / 2"
            :y="p.y - NODE_H / 2"
            :width="NODE_W"
            :height="NODE_H"
            :rx="NODE_RX"
            class="fill-emerald-500/10 stroke-emerald-500/40"
            stroke-width="1"
          />
          <text
            :x="p.x"
            :y="p.y + 4"
            text-anchor="middle"
            class="fill-emerald-700 dark:fill-emerald-300 text-xs"
          >
            {{ personaName(p.id).slice(0, 14) }}
          </text>
          <title>{{ personaName(p.id) }}</title>
        </a>
      </g>

      <!-- Centre node: current agent -->
      <g>
        <rect
          :x="CENTER_X - NODE_W / 2 - 10"
          :y="CENTER_Y - NODE_H / 2"
          :width="NODE_W + 20"
          :height="NODE_H"
          :rx="NODE_RX"
          class="fill-primary/15 stroke-primary"
          stroke-width="1.5"
        />
        <text
          :x="CENTER_X"
          :y="CENTER_Y + 4"
          text-anchor="middle"
          class="fill-primary text-sm font-semibold"
        >
          {{ props.agentName.slice(0, 16) }}
        </text>
      </g>

      <!-- Sibling agent nodes (bottom) -->
      <g
        v-for="s in siblingPositions"
        :key="`s-${s.id}`"
      >
        <a :href="`/agents/${s.id}`">
          <rect
            :x="s.x - NODE_W / 2"
            :y="s.y - NODE_H / 2"
            :width="NODE_W"
            :height="NODE_H"
            :rx="NODE_RX"
            class="fill-blue-500/10 stroke-blue-500/40"
            stroke-width="1"
          />
          <text
            :x="s.x"
            :y="s.y + 4"
            text-anchor="middle"
            class="fill-blue-700 dark:fill-blue-300 text-xs"
          >
            {{ s.id.slice(0, 14) }}
          </text>
          <title>{{ s.id }}</title>
        </a>
      </g>
    </svg>
    <p class="text-xs text-muted mt-2 italic">
      Top: linked personas · Centre: this agent · Bottom: siblings (other
      agents linking the same personas)
    </p>
  </div>
</template>
