<script setup lang="ts">
// Internal reference page for the ArkaOS Pulse design system.
// Every visual decision on this page comes from tokens in main.css —
// if something here needs a hardcoded value, the token set is incomplete.
const surfaces = [
  { name: 'bg', varName: '--ui-bg', role: 'Page void' },
  { name: 'bg-muted', varName: '--ui-bg-muted', role: 'Quiet sections' },
  { name: 'bg-elevated', varName: '--ui-bg-elevated', role: 'Cards, panels' },
  { name: 'bg-accented', varName: '--ui-bg-accented', role: 'Hover, selection' }
]

const arkaScale = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]

const semantics = [
  { label: 'live', class: 'bg-primary', meaning: 'Alive — live data, primary action' },
  { label: 'warning', class: 'bg-warning', meaning: 'Degraded, needs attention' },
  { label: 'error', class: 'bg-error', meaning: 'Failed, blocked' },
  { label: 'info', class: 'bg-info', meaning: 'Secondary data voice' }
]

const typeScale = [
  { size: 'text-4xl', px: '36', use: 'Page title', font: 'font-display' },
  { size: 'text-2xl', px: '24', use: 'Section heading', font: 'font-display' },
  { size: 'text-lg', px: '18', use: 'Card heading', font: 'font-display' },
  { size: 'text-base', px: '16', use: 'Body', font: 'font-sans' },
  { size: 'text-sm', px: '14', use: 'Secondary body', font: 'font-sans' },
  { size: 'text-xs', px: '12', use: 'Metadata', font: 'font-sans' }
]

const liveAgents = [
  { name: 'Paulo', dept: 'dev', status: 'executing', tasks: 12 },
  { name: 'Valentina', dept: 'brand', status: 'reviewing', tasks: 4 },
  { name: 'Marta', dept: 'quality', status: 'gate', tasks: 7 }
]

const streamKey = ref(0)
</script>

<template>
  <div class="mx-auto max-w-5xl px-6 py-12 space-y-16">
    <!-- Hero: the system introducing itself in its own vernacular -->
    <header class="space-y-4">
      <p class="arka-eyebrow">
        arka://design-system · v1
      </p>
      <h1 class="font-display text-4xl font-bold tracking-tight">
        ArkaOS Pulse
      </h1>
      <p class="max-w-2xl text-muted">
        The dashboard is a living system: green means alive, motion means
        data arriving, and silence means rest. Dark is the flagship mode.
      </p>
      <div class="arka-pulse-line max-w-2xl" aria-hidden="true" />
    </header>

    <!-- Surfaces -->
    <section class="space-y-4">
      <p class="arka-eyebrow">
        surfaces
      </p>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div
          v-for="s in surfaces"
          :key="s.name"
          class="rounded-lg border border-default p-4"
          :style="{ background: `var(${s.varName})` }"
        >
          <span class="arka-data block text-xs text-muted">{{ s.varName }}</span>
          <span class="mt-6 block text-sm">{{ s.role }}</span>
        </div>
      </div>
    </section>

    <!-- Brand scale -->
    <section class="space-y-4">
      <p class="arka-eyebrow">
        arka · signal green
      </p>
      <div class="flex overflow-hidden rounded-lg border border-default">
        <div
          v-for="step in arkaScale"
          :key="step"
          class="flex h-20 flex-1 items-end justify-center pb-2"
          :style="{ background: `var(--color-arka-${step})` }"
        >
          <span
            class="arka-data text-[10px]"
            :class="step < 500 ? 'text-carbon-950' : 'text-carbon-50'"
          >{{ step }}</span>
        </div>
      </div>
      <div class="grid gap-2 sm:grid-cols-2">
        <div
          v-for="s in semantics"
          :key="s.label"
          class="flex items-center gap-3 rounded-lg border border-default bg-elevated p-3"
        >
          <span class="size-3 rounded-full" :class="s.class" />
          <span class="arka-data text-xs uppercase">{{ s.label }}</span>
          <span class="text-sm text-muted">{{ s.meaning }}</span>
        </div>
      </div>
    </section>

    <!-- Typography -->
    <section class="space-y-4">
      <p class="arka-eyebrow">
        typography
      </p>
      <div class="space-y-3 rounded-lg border border-default bg-elevated p-6">
        <div
          v-for="t in typeScale"
          :key="t.size"
          class="flex items-baseline gap-6 border-b border-muted pb-3 last:border-0 last:pb-0"
        >
          <span class="arka-data w-10 shrink-0 text-xs text-muted">{{ t.px }}</span>
          <span :class="[t.size, t.font]" class="truncate">
            Agents ship, gates verify
          </span>
          <span class="ml-auto shrink-0 text-xs text-muted">{{ t.use }}</span>
        </div>
        <p class="arka-data pt-2 text-sm">
          data: 86 agents · 17 departments · uptime 99.98% · 142,842 tokens
        </p>
      </div>
    </section>

    <!-- Motion -->
    <section class="space-y-4">
      <p class="arka-eyebrow">
        motion · one rhythm
      </p>
      <div class="grid gap-3 sm:grid-cols-3">
        <UCard>
          <div class="flex items-center gap-3">
            <span class="arka-live-dot" />
            <div>
              <p class="text-sm font-medium">
                Pulse
              </p>
              <p class="text-xs text-muted">
                Only what is live may breathe
              </p>
            </div>
          </div>
        </UCard>
        <UCard>
          <div class="space-y-2">
            <p class="text-sm font-medium">
              Stream-in
            </p>
            <div :key="streamKey" class="space-y-1">
              <div
                v-for="(a, i) in liveAgents"
                :key="a.name"
                class="arka-stream-in flex items-center gap-2 text-xs"
                :style="{ animationDelay: `calc(var(--arka-stagger-step) * ${i})` }"
              >
                <span class="size-1.5 rounded-full bg-primary" />
                <span>{{ a.name }}</span>
                <span class="arka-data ml-auto text-muted">{{ a.status }}</span>
              </div>
            </div>
            <UButton size="xs" variant="ghost" @click="streamKey++">
              Replay
            </UButton>
          </div>
        </UCard>
        <UCard>
          <div class="space-y-2">
            <p class="text-sm font-medium">
              Durations
            </p>
            <p class="arka-data text-xs text-muted">
              fast 150ms · base 240ms · slow 400ms
            </p>
            <p class="text-xs text-muted">
              Enter decelerates, exit is 65% faster. Respects reduced motion.
            </p>
          </div>
        </UCard>
      </div>
    </section>

    <!-- Components in theme -->
    <section class="space-y-4">
      <p class="arka-eyebrow">
        components
      </p>
      <UCard>
        <div class="flex flex-wrap items-center gap-3">
          <UButton>Dispatch agent</UButton>
          <UButton variant="outline">
            Review
          </UButton>
          <UButton variant="ghost">
            Cancel
          </UButton>
          <UButton color="error" variant="soft">
            Stop run
          </UButton>
          <UBadge variant="subtle">
            APPROVED
          </UBadge>
          <UBadge color="warning" variant="subtle">
            PENDING
          </UBadge>
          <USwitch default-value />
        </div>
      </UCard>
      <UCard>
        <template #header>
          <div class="flex items-center gap-3">
            <span class="arka-live-dot" />
            <span class="font-display text-lg font-semibold">Live squad</span>
            <span class="arka-data ml-auto text-xs text-muted">3 active</span>
          </div>
        </template>
        <ul class="divide-y divide-default">
          <li
            v-for="a in liveAgents"
            :key="a.name"
            class="flex items-center gap-4 py-3 first:pt-0 last:pb-0"
          >
            <UAvatar :alt="a.name" size="sm" />
            <div>
              <p class="text-sm font-medium">
                {{ a.name }}
              </p>
              <p class="text-xs text-muted">
                {{ a.dept }}
              </p>
            </div>
            <span class="arka-data ml-auto text-xs">{{ a.tasks }} tasks</span>
            <UBadge variant="subtle" size="sm">
              {{ a.status }}
            </UBadge>
          </li>
        </ul>
      </UCard>
    </section>
  </div>
</template>
