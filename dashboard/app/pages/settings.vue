<script setup lang="ts">
interface ProfileResponse {
  version: string
  name: string
  language: string
  market: string
  role: string
  company: string
  projectsDir: string
  vaultPath: string
  created: string
  updated: string
  projects_dirs_list: string[]
}

const { fetchApi, apiBase } = useApi()
const toast = useToast()

// ─── Profile (PR63 v2.81.0) ─────────────────────────────────────────────

const {
  data: profile,
  status: profileStatus,
  error: profileError,
  refresh: refreshProfile,
} = await fetchApi<ProfileResponse>('/api/profile')

const profileDraft = ref({
  name: profile.value?.name ?? '',
  company: profile.value?.company ?? '',
  role: profile.value?.role ?? '',
  market: profile.value?.market ?? '',
  language: profile.value?.language ?? 'en',
  vaultPath: profile.value?.vaultPath ?? '',
  projectsDir: profile.value?.projectsDir ?? '',
})

watch(profile, (p) => {
  if (!p) return
  profileDraft.value = {
    name: p.name,
    company: p.company,
    role: p.role,
    market: p.market,
    language: p.language,
    vaultPath: p.vaultPath,
    projectsDir: p.projectsDir,
  }
}, { immediate: true })

const savingProfile = ref(false)

async function saveProfile() {
  savingProfile.value = true
  try {
    await $fetch<ProfileResponse>(`${apiBase}/api/profile`, {
      method: 'POST',
      body: profileDraft.value,
    })
    await refreshProfile()
    toast.add({
      title: 'Profile saved',
      description: 'Settings written to ~/.arkaos/profile.json',
      color: 'success',
    })
  } catch (err) {
    toast.add({
      title: 'Save failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    savingProfile.value = false
  }
}

const languageOptions = [
  { label: 'English', value: 'en' },
  { label: 'Português', value: 'pt' },
]

const roleOptions = [
  { label: 'Founder', value: 'founder' },
  { label: 'CTO', value: 'cto' },
  { label: 'CEO', value: 'ceo' },
  { label: 'Engineer', value: 'engineer' },
  { label: 'Designer', value: 'designer' },
  { label: 'Operator', value: 'operator' },
  { label: 'Consultant', value: 'consultant' },
]

// ─── API Keys (preserved from earlier) ──────────────────────────────────

const {
  data: keysData,
  status: keysStatus,
  refresh: refreshKeys,
} = fetchApi<any>('/api/keys')

const keys = computed(() => keysData.value?.keys ?? [])

const newKey = ref('')
const newValue = ref('')
const customKeyName = ref('')
const saving = ref(false)
const deletingKey = ref<string | null>(null)

const isCustom = computed(() => newKey.value === 'custom')
const effectiveKeyName = computed(() => isCustom.value ? customKeyName.value : newKey.value)

async function saveKey() {
  const keyName = effectiveKeyName.value
  if (!keyName || !newValue.value) return
  saving.value = true
  try {
    await $fetch(`${apiBase}/api/keys`, {
      method: 'POST',
      body: { key: keyName, value: newValue.value },
    })
    newKey.value = ''
    newValue.value = ''
    customKeyName.value = ''
    await refreshKeys()
  } catch {}
  saving.value = false
}

async function deleteKey(keyName: string) {
  deletingKey.value = keyName
  try {
    await $fetch(`${apiBase}/api/keys/${keyName}`, { method: 'DELETE' })
    await refreshKeys()
  } catch {}
  deletingKey.value = null
}

const keyOptions = [
  { label: 'OPENAI_API_KEY', value: 'OPENAI_API_KEY' },
  { label: 'FAL_API_KEY', value: 'FAL_API_KEY' },
  { label: 'GOOGLE_API_KEY', value: 'GOOGLE_API_KEY' },
  { label: 'Custom...', value: 'custom' },
]

// ─── Section nav ────────────────────────────────────────────────────────

type SectionId = 'profile' | 'projects' | 'keys'

const sections: { id: SectionId; label: string; icon: string }[] = [
  { id: 'profile', label: 'Profile', icon: 'i-lucide-user-circle' },
  { id: 'projects', label: 'Projects', icon: 'i-lucide-folders' },
  { id: 'keys', label: 'API Keys', icon: 'i-lucide-key' },
]

const activeSection = ref<SectionId>('profile')
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
      <div class="grid grid-cols-1 md:grid-cols-[14rem_1fr] gap-6">
        <!-- Section nav -->
        <nav class="space-y-1" aria-label="Settings sections">
          <button
            v-for="s in sections"
            :key="s.id"
            type="button"
            class="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors"
            :class="activeSection === s.id
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-muted hover:bg-elevated/50'"
            @click="activeSection = s.id"
          >
            <UIcon :name="s.icon" class="size-4" />
            <span>{{ s.label }}</span>
          </button>
          <p class="text-xs text-muted px-3 mt-6">
            More sections (MCPs, Hooks, Plugins, Theme) coming in PR63b.
          </p>
        </nav>

        <!-- Section content -->
        <div>
          <!-- Profile -->
          <section v-if="activeSection === 'profile'">
            <h2 class="text-lg font-semibold mb-1">Profile</h2>
            <p class="text-sm text-muted mb-6">
              Your identity, role, and language. Stored locally at
              <code class="font-mono text-xs">~/.arkaos/profile.json</code>.
            </p>

            <DashboardState
              :status="profileStatus"
              :error="profileError"
              loading-label="Loading profile"
              :on-retry="() => refreshProfile()"
            >
              <UCard>
                <div class="space-y-4">
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <UFormField label="Name">
                      <UInput
                        v-model="profileDraft.name"
                        placeholder="André Agro Ferreira"
                        class="w-full"
                      />
                    </UFormField>
                    <UFormField label="Company">
                      <UInput
                        v-model="profileDraft.company"
                        placeholder="WizardingCode"
                        class="w-full"
                      />
                    </UFormField>
                  </div>

                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <UFormField label="Role">
                      <USelect
                        v-model="profileDraft.role"
                        :items="roleOptions"
                        placeholder="Select role"
                        class="w-full"
                      />
                    </UFormField>
                    <UFormField label="Language">
                      <USelect
                        v-model="profileDraft.language"
                        :items="languageOptions"
                        class="w-full"
                      />
                    </UFormField>
                  </div>

                  <UFormField
                    label="Market"
                    help="Comma-separated list of markets you operate in (free text)."
                  >
                    <UInput
                      v-model="profileDraft.market"
                      placeholder="Portugal, Europa, Emirados Árabes Unidos"
                      class="w-full"
                    />
                  </UFormField>

                  <UFormField
                    label="Vault path"
                    help="Where your Obsidian vault lives. Used by the KB-first hook."
                  >
                    <UInput
                      v-model="profileDraft.vaultPath"
                      placeholder="/Users/you/Documents/Vault"
                      class="w-full font-mono text-sm"
                    />
                  </UFormField>

                  <div class="flex justify-end pt-2">
                    <UButton
                      label="Save profile"
                      icon="i-lucide-check"
                      :loading="savingProfile"
                      @click="saveProfile"
                    />
                  </div>
                </div>
              </UCard>
            </DashboardState>
          </section>

          <!-- Projects -->
          <section v-else-if="activeSection === 'projects'">
            <h2 class="text-lg font-semibold mb-1">Project directories</h2>
            <p class="text-sm text-muted mb-6">
              Directories the sync engine scans for projects.
              Comma-separated absolute paths (e.g.
              <code class="font-mono text-xs">~/Herd</code>,
              <code class="font-mono text-xs">~/Work</code>).
            </p>

            <UCard>
              <div class="space-y-4">
                <UFormField
                  label="projectsDir"
                  help="Free text. Each comma-separated segment's leading absolute path is consumed by the sync engine."
                >
                  <UTextarea
                    v-model="profileDraft.projectsDir"
                    :rows="3"
                    placeholder="/Users/you/Herd para projectos laravel, /Users/you/Work para projectos Nuxt e Python"
                    class="w-full font-mono text-sm"
                  />
                </UFormField>

                <div v-if="profile?.projects_dirs_list?.length" class="rounded-lg border border-default p-3">
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                    Currently parsed
                  </p>
                  <ul class="space-y-1">
                    <li
                      v-for="dir in profile.projects_dirs_list"
                      :key="dir"
                      class="flex items-center gap-2 text-sm"
                    >
                      <UIcon name="i-lucide-folder" class="size-4 text-muted" />
                      <code class="font-mono text-xs">{{ dir }}</code>
                    </li>
                  </ul>
                </div>

                <div class="flex justify-end pt-2">
                  <UButton
                    label="Save directories"
                    icon="i-lucide-check"
                    :loading="savingProfile"
                    @click="saveProfile"
                  />
                </div>
              </div>
            </UCard>
          </section>

          <!-- API Keys -->
          <section v-else-if="activeSection === 'keys'">
            <h2 class="text-lg font-semibold mb-1">API Keys</h2>
            <p class="text-sm text-muted mb-6">
              Configure API keys for external services. Keys are stored
              locally at <code class="font-mono text-xs">~/.arkaos/keys.json</code>.
            </p>

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
                      block
                      @click="saveKey"
                    />
                  </div>
                </div>
              </div>
            </UCard>

            <DashboardState
              :status="keysStatus"
              :empty="!keys.length"
              empty-title="No keys configured"
              empty-icon="i-lucide-key"
              loading-label="Loading API keys"
            >
              <div class="space-y-2">
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
                      <UBadge v-else label="Not Set" color="neutral" variant="outline" size="xs" />
                    </div>
                    <p v-if="k.used_for" class="text-xs text-muted mt-0.5">{{ k.used_for }}</p>
                    <p v-if="k.masked_value && k.configured" class="text-xs font-mono text-muted/60 mt-0.5">
                      {{ k.masked_value }}
                    </p>
                  </div>
                  <UButton
                    v-if="k.configured && k.masked_value !== '(from environment)'"
                    icon="i-lucide-trash-2"
                    variant="ghost"
                    color="error"
                    size="xs"
                    :loading="deletingKey === k.key"
                    aria-label="Delete key"
                    @click="deleteKey(k.key)"
                  />
                </div>
              </div>
            </DashboardState>
          </section>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
