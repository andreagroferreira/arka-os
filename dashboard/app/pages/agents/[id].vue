<script setup lang="ts">
const route = useRoute()
const agentId = route.params.id as string

const { fetchApi } = useApi()
const { data: agent, status, error } = fetchApi<any>(`/api/agents/${agentId}`)

// --- Labels & mappings ---

const tierLabel: Record<number, string> = {
  0: 'C-Suite',
  1: 'Squad Lead',
  2: 'Specialist',
  3: 'Support',
}

const tierColor: Record<number, string> = {
  0: 'error',
  1: 'warning',
  2: 'primary',
  3: 'neutral',
}

const depthColor: Record<string, string> = {
  master: 'error',
  expert: 'warning',
  advanced: 'primary',
  intermediate: 'neutral',
}

const bigFiveLabels: Record<string, string> = {
  O: 'Openness',
  C: 'Conscientiousness',
  E: 'Extraversion',
  A: 'Agreeableness',
  N: 'Neuroticism',
}

const bigFiveKeys = ['O', 'C', 'E', 'A', 'N'] as const

const mbtiDescriptions: Record<string, string> = {
  INTJ: 'Ni-Te-Fi-Se — The Architect',
  INTP: 'Ti-Ne-Si-Fe — The Logician',
  ENTJ: 'Te-Ni-Se-Fi — The Commander',
  ENTP: 'Ne-Ti-Fe-Si — The Debater',
  INFJ: 'Ni-Fe-Ti-Se — The Advocate',
  INFP: 'Fi-Ne-Si-Te — The Mediator',
  ENFJ: 'Fe-Ni-Se-Ti — The Protagonist',
  ENFP: 'Ne-Fi-Te-Si — The Campaigner',
  ISTJ: 'Si-Te-Fi-Ne — The Inspector',
  ISFJ: 'Si-Fe-Ti-Ne — The Defender',
  ESTJ: 'Te-Si-Ne-Fi — The Executive',
  ESFJ: 'Fe-Si-Ne-Ti — The Consul',
  ISTP: 'Ti-Se-Ni-Fe — The Virtuoso',
  ISFP: 'Fi-Se-Ni-Te — The Adventurer',
  ESTP: 'Se-Ti-Fe-Ni — The Entrepreneur',
  ESFP: 'Se-Fi-Te-Ni — The Entertainer',
}

// --- DISC bar values ---

const discLetters = ['D', 'I', 'S', 'C'] as const

function discBarValue(letter: string): number {
  if (!agent.value?.disc) return 20
  if (agent.value.disc.primary === letter) return 90
  if (agent.value.disc.secondary === letter) return 70
  return 20
}

function discBarColor(letter: string): string {
  const colors: Record<string, string> = {
    D: 'bg-red-500',
    I: 'bg-yellow-500',
    S: 'bg-green-500',
    C: 'bg-blue-500',
  }
  return colors[letter] ?? 'bg-primary'
}

function bigFiveBarColor(value: number): string {
  if (value >= 75) return 'bg-primary'
  if (value >= 50) return 'bg-blue-400'
  if (value >= 30) return 'bg-yellow-500'
  return 'bg-neutral-500'
}

// --- Tabs ---

const tabs = [
  { label: 'DNA', value: 'dna', icon: 'i-lucide-dna' },
  { label: 'Communication', value: 'communication', icon: 'i-lucide-message-square' },
  { label: 'Mental Models', value: 'models', icon: 'i-lucide-brain' },
  { label: 'Authority', value: 'authority', icon: 'i-lucide-shield' },
  { label: 'Expertise', value: 'expertise', icon: 'i-lucide-award' },
]
</script>

<template>
  <UDashboardPanel id="agent-detail">
    <template #header>
      <UDashboardNavbar :title="agent?.name ?? 'Agent'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UButton
            label="Back"
            variant="ghost"
            icon="i-lucide-arrow-left"
            to="/agents"
            aria-label="Back to agents list"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-24">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-24" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load agent data.</p>
        <UButton label="Back to Agents" variant="outline" icon="i-lucide-arrow-left" to="/agents" />
      </div>

      <!-- Not found -->
      <div v-else-if="!agent" class="flex flex-col items-center justify-center gap-4 py-24">
        <UIcon name="i-lucide-user-x" class="size-12 text-muted" />
        <p class="text-sm text-muted">Agent not found.</p>
        <UButton label="Back to Agents" variant="outline" icon="i-lucide-arrow-left" to="/agents" />
      </div>

      <!-- Content -->
      <div v-else class="space-y-8 pb-12">
        <!-- ===== HEADER SECTION ===== -->
        <section class="space-y-3">
          <h1 class="text-3xl font-bold tracking-tight">{{ agent.name }}</h1>
          <p class="text-lg text-muted">{{ agent.role }}</p>

          <div class="flex flex-wrap items-center gap-2">
            <UBadge :label="agent.department" variant="subtle" />
            <UBadge
              :label="`Tier ${agent.tier} — ${tierLabel[agent.tier] ?? ''}`"
              variant="subtle"
              :color="(tierColor[agent.tier] ?? 'neutral') as any"
            />
            <UBadge
              v-if="agent.expertise_depth"
              :label="agent.expertise_depth"
              variant="subtle"
              :color="(depthColor[agent.expertise_depth] ?? 'neutral') as any"
            />
            <UBadge
              v-if="agent.expertise_years"
              :label="`${agent.expertise_years}y experience`"
              variant="outline"
            />
          </div>

          <p class="text-xs text-muted/60 font-mono select-all">{{ agent.id }}</p>
        </section>

        <!-- ===== TABS ===== -->
        <UTabs :items="tabs" class="w-full">
          <template #content="{ item }">
            <!-- ===== TAB: DNA ===== -->
            <div v-if="item.value === 'dna'" class="space-y-6 mt-6">
              <!-- DNA Summary — 3 cards -->
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Card 1: MBTI -->
                <UCard>
                  <div class="space-y-2">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">MBTI</p>
                    <p class="text-4xl font-bold font-mono tracking-widest">
                      {{ agent.mbti || '----' }}
                    </p>
                    <p v-if="agent.mbti && mbtiDescriptions[agent.mbti]" class="text-sm text-muted">
                      {{ mbtiDescriptions[agent.mbti] }}
                    </p>
                  </div>
                </UCard>

                <!-- Card 2: Enneagram -->
                <UCard>
                  <div class="space-y-3">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">Enneagram</p>
                    <div>
                      <p class="text-3xl font-bold">
                        Type {{ agent.enneagram?.type ?? '-' }}
                        <span v-if="agent.enneagram?.wing" class="text-xl font-normal text-muted">
                          w{{ agent.enneagram.wing }}
                        </span>
                      </p>
                      <p v-if="agent.enneagram?.label" class="text-sm text-muted mt-1">
                        {{ agent.enneagram.label }}
                      </p>
                    </div>

                    <div class="grid grid-cols-2 gap-2 pt-1">
                      <div class="rounded-lg bg-red-500/10 border border-red-500/20 p-2.5">
                        <p class="text-[10px] font-bold text-red-400 uppercase tracking-wider mb-1">Fear</p>
                        <p class="text-xs text-muted leading-snug">
                          {{ agent.enneagram?.core_fear ?? 'Unknown' }}
                        </p>
                      </div>
                      <div class="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-2.5">
                        <p class="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1">Drive</p>
                        <p class="text-xs text-muted leading-snug">
                          {{ agent.enneagram?.core_motivation ?? 'Unknown' }}
                        </p>
                      </div>
                    </div>
                  </div>
                </UCard>

                <!-- Card 3: DISC -->
                <UCard>
                  <div class="space-y-3">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">DISC</p>
                    <div>
                      <p class="text-3xl font-bold font-mono">
                        {{ agent.disc?.primary ?? '' }}{{ agent.disc?.secondary ?? '' }}
                      </p>
                      <p v-if="agent.disc?.label" class="text-sm text-muted mt-1">
                        {{ agent.disc.label }}
                      </p>
                    </div>

                    <div class="space-y-2 pt-1">
                      <div v-for="letter in discLetters" :key="letter" class="flex items-center gap-2">
                        <span class="w-4 text-xs font-mono font-bold text-muted">{{ letter }}</span>
                        <div class="flex-1 h-2 rounded-full bg-muted/20">
                          <div
                            class="h-2 rounded-full transition-none"
                            :class="discBarColor(letter)"
                            :style="{ width: `${discBarValue(letter)}%` }"
                          />
                        </div>
                        <span class="w-6 text-right text-xs font-mono text-muted">
                          {{ discBarValue(letter) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </UCard>
              </div>

              <!-- Big Five -->
              <UCard>
                <div class="space-y-1">
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-4">
                    Big Five (OCEAN)
                  </p>
                  <div v-if="agent.big_five" class="space-y-3">
                    <div
                      v-for="key in bigFiveKeys"
                      :key="key"
                      class="flex items-center gap-3"
                    >
                      <span class="w-36 text-sm text-muted">{{ bigFiveLabels[key] }}</span>
                      <div class="flex-1 h-2 rounded-full bg-muted/20">
                        <div
                          class="h-2 rounded-full transition-none"
                          :class="bigFiveBarColor(agent.big_five[key] ?? 0)"
                          :style="{ width: `${agent.big_five[key] ?? 0}%` }"
                        />
                      </div>
                      <span class="w-8 text-right text-sm font-mono">
                        {{ agent.big_five[key] ?? 0 }}
                      </span>
                    </div>
                  </div>
                  <p v-else class="text-sm text-muted">No Big Five data available.</p>
                </div>
              </UCard>
            </div>

            <!-- ===== TAB: COMMUNICATION ===== -->
            <div v-else-if="item.value === 'communication'" class="space-y-4 mt-6">
              <div v-if="agent.communication" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UCard>
                  <div class="space-y-4">
                    <div>
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Tone</p>
                      <p class="text-sm">{{ agent.communication.tone ?? '-' }}</p>
                    </div>
                    <div>
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Vocabulary Level</p>
                      <UBadge :label="agent.communication.vocabulary_level ?? '-'" variant="subtle" />
                    </div>
                    <div>
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Language</p>
                      <p class="text-sm font-mono">{{ agent.communication.language ?? '-' }}</p>
                    </div>
                  </div>
                </UCard>

                <UCard>
                  <div class="space-y-4">
                    <div>
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Preferred Format</p>
                      <p class="text-sm">{{ agent.communication.preferred_format ?? '-' }}</p>
                    </div>
                    <div v-if="agent.communication.avoid?.length">
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Avoids</p>
                      <ul class="space-y-1.5">
                        <li
                          v-for="item in agent.communication.avoid"
                          :key="item"
                          class="flex items-start gap-2 text-sm text-muted"
                        >
                          <UIcon name="i-lucide-x" class="size-4 text-red-400 mt-0.5 shrink-0" />
                          {{ item }}
                        </li>
                      </ul>
                    </div>
                  </div>
                </UCard>
              </div>

              <!-- DISC Communication Details -->
              <UCard v-if="agent.disc?.communication_style || agent.disc?.under_pressure || agent.disc?.motivator">
                <div class="space-y-4">
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider">DISC Communication Profile</p>
                  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div v-if="agent.disc.communication_style">
                      <p class="text-xs text-muted mb-1">Communication Style</p>
                      <p class="text-sm">{{ agent.disc.communication_style }}</p>
                    </div>
                    <div v-if="agent.disc.under_pressure">
                      <p class="text-xs text-muted mb-1">Under Pressure</p>
                      <p class="text-sm">{{ agent.disc.under_pressure }}</p>
                    </div>
                    <div v-if="agent.disc.motivator">
                      <p class="text-xs text-muted mb-1">Motivator</p>
                      <p class="text-sm">{{ agent.disc.motivator }}</p>
                    </div>
                  </div>
                </div>
              </UCard>

              <div v-if="!agent.communication && !agent.disc?.communication_style" class="py-8 text-center">
                <p class="text-sm text-muted">No communication data available.</p>
              </div>
            </div>

            <!-- ===== TAB: MENTAL MODELS ===== -->
            <div v-else-if="item.value === 'models'" class="space-y-4 mt-6">
              <div v-if="agent.mental_models" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UCard>
                  <div class="space-y-3">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">Primary Models</p>
                    <ul v-if="agent.mental_models.primary?.length" class="space-y-2">
                      <li
                        v-for="model in agent.mental_models.primary"
                        :key="model"
                        class="flex items-center gap-2"
                      >
                        <div class="size-1.5 rounded-full bg-primary shrink-0" />
                        <span class="text-sm font-medium">{{ model }}</span>
                      </li>
                    </ul>
                    <p v-else class="text-sm text-muted">None listed.</p>
                  </div>
                </UCard>

                <UCard>
                  <div class="space-y-3">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">Secondary Models</p>
                    <ul v-if="agent.mental_models.secondary?.length" class="space-y-2">
                      <li
                        v-for="model in agent.mental_models.secondary"
                        :key="model"
                        class="flex items-center gap-2"
                      >
                        <div class="size-1.5 rounded-full bg-muted/40 shrink-0" />
                        <span class="text-sm text-muted">{{ model }}</span>
                      </li>
                    </ul>
                    <p v-else class="text-sm text-muted">None listed.</p>
                  </div>
                </UCard>
              </div>

              <div v-else class="py-8 text-center">
                <p class="text-sm text-muted">No mental model data available.</p>
              </div>
            </div>

            <!-- ===== TAB: AUTHORITY ===== -->
            <div v-else-if="item.value === 'authority'" class="space-y-4 mt-6">
              <div v-if="agent.authority">
                <UCard>
                  <div class="space-y-5">
                    <div>
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Permissions</p>
                      <div class="flex flex-wrap gap-2">
                        <UBadge v-if="agent.authority.veto" label="Veto" color="error" variant="subtle" />
                        <UBadge v-if="agent.authority.approve_architecture" label="Approve Architecture" color="success" variant="subtle" />
                        <UBadge v-if="agent.authority.approve_budget" label="Approve Budget" color="success" variant="subtle" />
                        <UBadge v-if="agent.authority.approve_quality" label="Approve Quality" color="success" variant="subtle" />
                        <UBadge v-if="agent.authority.block_release" label="Block Release" color="error" variant="subtle" />
                        <UBadge v-if="agent.authority.orchestrate" label="Orchestrate" color="primary" variant="subtle" />
                      </div>
                    </div>

                    <div v-if="agent.authority.delegates_to?.length">
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Delegates To</p>
                      <div class="flex flex-wrap gap-2">
                        <UBadge
                          v-for="d in agent.authority.delegates_to"
                          :key="d"
                          :label="d"
                          variant="outline"
                          size="sm"
                        />
                      </div>
                    </div>

                    <div v-if="agent.authority.escalates_to">
                      <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Escalates To</p>
                      <p class="text-sm font-mono">{{ agent.authority.escalates_to }}</p>
                    </div>

                    <div v-if="!agent.authority.escalates_to && !agent.authority.delegates_to?.length && !agent.authority.veto">
                      <p class="text-sm text-muted">Standard execution authority.</p>
                    </div>
                  </div>
                </UCard>
              </div>

              <div v-else class="py-8 text-center">
                <p class="text-sm text-muted">No authority data available.</p>
              </div>
            </div>

            <!-- ===== TAB: EXPERTISE ===== -->
            <div v-else-if="item.value === 'expertise'" class="space-y-4 mt-6">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UCard>
                  <div class="space-y-3">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">Domains</p>
                    <div v-if="agent.expertise_domains?.length" class="flex flex-wrap gap-2">
                      <UBadge
                        v-for="d in agent.expertise_domains"
                        :key="d"
                        :label="d"
                        color="primary"
                        variant="subtle"
                        size="sm"
                      />
                    </div>
                    <p v-else class="text-sm text-muted">No domains listed.</p>
                  </div>
                </UCard>

                <UCard>
                  <div class="space-y-3">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider">Frameworks</p>
                    <ul v-if="agent.frameworks?.length" class="space-y-2">
                      <li
                        v-for="f in agent.frameworks"
                        :key="f"
                        class="flex items-center gap-2 text-sm"
                      >
                        <UIcon name="i-lucide-check" class="size-3.5 text-primary shrink-0" />
                        {{ f }}
                      </li>
                    </ul>
                    <p v-else class="text-sm text-muted">No frameworks listed.</p>
                  </div>
                </UCard>
              </div>

              <UCard v-if="agent.expertise_depth || agent.expertise_years">
                <div class="flex flex-wrap gap-6">
                  <div v-if="agent.expertise_depth">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Depth</p>
                    <UBadge
                      :label="agent.expertise_depth"
                      :color="(depthColor[agent.expertise_depth] ?? 'neutral') as any"
                      variant="subtle"
                      size="lg"
                    />
                  </div>
                  <div v-if="agent.expertise_years">
                    <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">Experience</p>
                    <p class="text-2xl font-bold">
                      {{ agent.expertise_years }}
                      <span class="text-sm font-normal text-muted">years</span>
                    </p>
                  </div>
                </div>
              </UCard>
            </div>
          </template>
        </UTabs>
      </div>
    </template>
  </UDashboardPanel>
</template>
