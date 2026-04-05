<script setup lang="ts">
const { fetchApi, apiBase } = useApi()

const { data, status, error, refresh } = fetchApi<any>('/api/keys')

const keys = computed(() => data.value?.keys ?? [])

const newKey = ref('')
const newValue = ref('')
const saving = ref(false)
const deletingKey = ref<string | null>(null)

async function saveKey() {
  if (!newKey.value || !newValue.value) return
  saving.value = true
  try {
    await $fetch(`${apiBase}/api/keys`, {
      method: 'POST',
      body: { key: newKey.value, value: newValue.value },
    })
    newKey.value = ''
    newValue.value = ''
    await refresh()
  } catch {}
  saving.value = false
}

async function deleteKey(keyName: string) {
  deletingKey.value = keyName
  try {
    await $fetch(`${apiBase}/api/keys/${keyName}`, { method: 'DELETE' })
    await refresh()
  } catch {}
  deletingKey.value = null
}

const keyOptions = [
  { label: 'OPENAI_API_KEY', value: 'OPENAI_API_KEY' },
  { label: 'FAL_API_KEY', value: 'FAL_API_KEY' },
  { label: 'ANTHROPIC_API_KEY', value: 'ANTHROPIC_API_KEY' },
  { label: 'Custom...', value: 'custom' },
]

const isCustom = computed(() => newKey.value === 'custom')
const customKeyName = ref('')
const effectiveKeyName = computed(() => isCustom.value ? customKeyName.value : newKey.value)
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="Settings">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-8">
        <!-- API Keys Section -->
        <div>
          <h2 class="text-lg font-semibold mb-1">API Keys</h2>
          <p class="text-sm text-muted mb-6">Configure API keys for external services. Keys are stored locally at ~/.arkaos/keys.json.</p>

          <!-- Add Key Form -->
          <UCard class="mb-6">
            <div class="space-y-4">
              <p class="text-xs font-semibold text-muted uppercase tracking-wider">Add API Key</p>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                <div>
                  <label class="text-xs text-muted mb-1 block">Provider</label>
                  <USelect v-model="newKey" :items="keyOptions" class="w-full" placeholder="Select key..." />
                </div>
                <div v-if="isCustom">
                  <label class="text-xs text-muted mb-1 block">Key Name</label>
                  <UInput v-model="customKeyName" class="w-full" placeholder="MY_CUSTOM_KEY" />
                </div>
                <div :class="isCustom ? '' : 'md:col-span-1'">
                  <label class="text-xs text-muted mb-1 block">Value</label>
                  <UInput v-model="newValue" type="password" class="w-full" placeholder="sk-..." />
                </div>
                <div>
                  <UButton
                    label="Save Key"
                    icon="i-lucide-key"
                    :loading="saving"
                    :disabled="!effectiveKeyName || !newValue"
                    @click="() => { newKey = effectiveKeyName; saveKey() }"
                    block
                  />
                </div>
              </div>
            </div>
          </UCard>

          <!-- Keys List -->
          <div v-if="status === 'pending'" class="flex items-center justify-center py-8">
            <UIcon name="i-lucide-loader-2" class="size-6 animate-spin text-muted" />
          </div>

          <div v-else class="space-y-2">
            <div
              v-for="k in keys"
              :key="k.key"
              class="flex items-center gap-4 p-3 rounded-lg border border-default"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-mono font-medium">{{ k.key }}</span>
                  <UBadge :label="k.provider" variant="subtle" size="xs" />
                  <UBadge
                    v-if="k.configured"
                    label="Configured"
                    color="success"
                    variant="subtle"
                    size="xs"
                  />
                  <UBadge
                    v-else
                    label="Not Set"
                    color="neutral"
                    variant="outline"
                    size="xs"
                  />
                </div>
                <p v-if="k.used_for" class="text-xs text-muted mt-0.5">{{ k.used_for }}</p>
                <p v-if="k.masked_value && k.configured" class="text-xs font-mono text-muted/60 mt-0.5">{{ k.masked_value }}</p>
              </div>
              <UButton
                v-if="k.configured && k.masked_value !== '(from environment)'"
                icon="i-lucide-trash-2"
                variant="ghost"
                color="error"
                size="xs"
                :loading="deletingKey === k.key"
                @click="deleteKey(k.key)"
                aria-label="Delete key"
              />
            </div>
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
