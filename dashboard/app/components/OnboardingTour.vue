<script setup lang="ts">
// PR92c v3.41.0 — first-visit onboarding tour.
//
// One-shot modal that shows up on the home page until the operator
// dismisses it. Walks through Agents → Personas → Workflows → Budget.
// Dismissal persists in localStorage as `arkaos_onboarding_dismissed`.

const open = ref(false)
const step = ref(0)
const router = useRouter()
const route = useRoute()

const STORAGE_KEY = 'arkaos_onboarding_dismissed'

interface TourStep {
  icon: string
  title: string
  body: string
  cta?: { label: string, to: string }
}

const steps: TourStep[] = [
  {
    icon: 'i-lucide-sparkles',
    title: 'Welcome to ArkaOS',
    body: 'A 4-minute tour of where to start. Press Esc anytime to skip — you can replay this from Settings.',
  },
  {
    icon: 'i-lucide-users',
    title: 'Agents',
    body: 'Your specialist team. Browse the table, click a row for full detail (DNA, expertise, history). Create new ones with the AI draft on /agents/new.',
    cta: { label: 'Open /agents', to: '/agents' },
  },
  {
    icon: 'i-lucide-user-plus',
    title: 'Personas',
    body: 'Behavioural profiles of real people (or archetypes) that seed your agents. Import from .md files / URLs, export as ZIP, clone to agents.',
    cta: { label: 'Open /personas', to: '/personas' },
  },
  {
    icon: 'i-lucide-workflow',
    title: 'Workflows',
    body: 'YAML-defined orchestrations under departments/. Click a workflow for its phase flow, raw YAML, and recent runs.',
    cta: { label: 'Open /workflows', to: '/workflows' },
  },
  {
    icon: 'i-lucide-wallet',
    title: 'Budget',
    body: 'Real LLM spend by provider/model/category, daily trend chart (7/14/30d), CSV export. Powered by PR47 telemetry.',
    cta: { label: 'Open /budget', to: '/budget' },
  },
  {
    icon: 'i-lucide-keyboard',
    title: 'Power shortcuts',
    body: 'Press ? anywhere for the full keymap. Try / for search, g a for agents, g p for personas.',
  },
]

onMounted(() => {
  if (typeof window === 'undefined') return
  if (window.localStorage.getItem(STORAGE_KEY) === '1') return
  // Only auto-open on the home route — operators clicking around shouldn't
  // be interrupted.
  if (route.path !== '/') return
  open.value = true
})

function next() {
  if (step.value < steps.length - 1) {
    step.value += 1
  } else {
    dismiss()
  }
}

function back() {
  if (step.value > 0) step.value -= 1
}

function dismiss() {
  open.value = false
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, '1')
  }
}

function navigateAndDismiss(to: string) {
  dismiss()
  router.push(to)
}

const current = computed(() => steps[step.value])
const progress = computed(() => Math.round(((step.value + 1) / steps.length) * 100))
</script>

<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'max-w-lg' }"
    title="Welcome"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <UIcon :name="current.icon" class="size-6 text-primary" />
              <div>
                <h2 class="text-lg font-bold">{{ current.title }}</h2>
                <p class="text-xs text-muted mt-0.5">
                  Step {{ step + 1 }} of {{ steps.length }}
                </p>
              </div>
            </div>
            <UButton icon="i-lucide-x" variant="ghost" size="sm" aria-label="Skip" @click="dismiss" />
          </div>
        </template>

        <div class="space-y-4">
          <p class="text-sm">{{ current.body }}</p>
          <UButton
            v-if="current.cta"
            :label="current.cta.label"
            :icon="current.icon"
            variant="soft"
            color="primary"
            @click="navigateAndDismiss(current.cta!.to)"
          />
          <div class="h-1.5 rounded-full bg-elevated/40 overflow-hidden">
            <div
              class="h-1.5 rounded-full bg-primary transition-all duration-200"
              :style="{ width: `${progress}%` }"
            />
          </div>
        </div>

        <template #footer>
          <div class="flex items-center justify-between gap-2 text-xs">
            <UButton
              label="Don't show again"
              variant="ghost"
              size="xs"
              @click="dismiss"
            />
            <div class="flex items-center gap-2">
              <UButton
                v-if="step > 0"
                label="Back"
                variant="ghost"
                size="sm"
                @click="back"
              />
              <UButton
                :label="step === steps.length - 1 ? 'Finish' : 'Next'"
                icon="i-lucide-arrow-right"
                size="sm"
                @click="next"
              />
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
