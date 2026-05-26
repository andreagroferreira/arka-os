<script setup lang="ts">
// PR85a v3.11.0 — Clone Persona → Agent dialog.
//
// Wraps POST /api/personas/{id}/clone in a modal. Operator picks
// department + tier, confirms, and the new agent is created. Parent
// navigates to /agents/{new_id} on success.

const props = defineProps<{
  modelValue: boolean
  personaId: string
  personaName: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'cloned', agentId: string): void
}>()

const { apiBase } = useApi()
const toast = useToast()

const department = ref('strategy')
const tier = ref<1 | 2 | 3>(2)
const cloning = ref(false)

const departmentOptions = [
  'dev', 'marketing', 'brand', 'finance', 'strategy', 'ecom', 'kb', 'ops',
  'pm', 'saas', 'landing', 'content', 'community', 'sales', 'leadership', 'org',
].map((d) => ({ label: d, value: d }))

const tierOptions = [
  { label: 'Tier 1 — Squad Lead', value: 1 },
  { label: 'Tier 2 — Specialist', value: 2 },
  { label: 'Tier 3 — Support', value: 3 },
]

async function clone() {
  cloning.value = true
  try {
    const res = await $fetch<{
      agent_id?: string
      department?: string
      file?: string
      error?: string
    }>(`${apiBase}/api/personas/${props.personaId}/clone`, {
      method: 'POST',
      body: { department: department.value, tier: tier.value },
    })
    if (res.error || !res.agent_id) throw new Error(res.error ?? 'unknown error')
    toast.add({
      title: 'Cloned to agent',
      description: `${props.personaName} → ${res.agent_id} (${res.department})`,
      color: 'success',
      icon: 'i-lucide-copy-plus',
    })
    emit('cloned', res.agent_id)
    emit('update:modelValue', false)
  } catch (err) {
    toast.add({
      title: 'Clone failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    cloning.value = false
  }
}

function close() {
  if (!cloning.value) emit('update:modelValue', false)
}
</script>

<template>
  <UModal
    :open="modelValue"
    title="Clone to Agent"
    :ui="{ content: 'max-w-md' }"
    @update:open="(v) => v ? null : close()"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-bold">Clone to Agent</h2>
              <p class="text-sm text-muted mt-0.5">
                Create a new agent based on <strong>{{ personaName }}</strong>.
              </p>
            </div>
            <UButton
              icon="i-lucide-x"
              variant="ghost"
              size="sm"
              aria-label="Close"
              :disabled="cloning"
              @click="close"
            />
          </div>
        </template>

        <div class="space-y-4">
          <UFormField label="Department" required>
            <USelect v-model="department" :items="departmentOptions" class="w-full" />
          </UFormField>
          <UFormField label="Tier" required>
            <USelect v-model="tier" :items="tierOptions" class="w-full" />
          </UFormField>
          <p class="rounded-lg border border-primary/30 bg-primary/5 p-3 text-xs text-muted">
            <UIcon name="i-lucide-info" class="size-3.5 inline" />
            The agent inherits the persona's behavioural DNA (DISC, Enneagram,
            MBTI, Big Five), mental models, expertise, and frameworks. You can
            edit it freely after creation.
          </p>
        </div>

        <template #footer>
          <div class="flex items-center justify-end gap-2">
            <UButton label="Cancel" variant="ghost" :disabled="cloning" @click="close" />
            <UButton
              label="Clone"
              icon="i-lucide-copy-plus"
              color="primary"
              :loading="cloning"
              @click="clone"
            />
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
