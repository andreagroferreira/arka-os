<script setup lang="ts">
// PR92d v3.42.0 — primary color picker.
import { THEME_COLOR_OPTIONS, useThemeColor } from '~/composables/useThemeColor'

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
  refresh: refreshProfile
} = await fetchApi<ProfileResponse>('/api/profile')

const profileDraft = ref({
  name: profile.value?.name ?? '',
  company: profile.value?.company ?? '',
  role: profile.value?.role ?? '',
  market: profile.value?.market ?? '',
  language: profile.value?.language ?? 'en',
  vaultPath: profile.value?.vaultPath ?? '',
  projectsDir: profile.value?.projectsDir ?? ''
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
    projectsDir: p.projectsDir
  }
}, { immediate: true })

const savingProfile = ref(false)

// PR89c v3.29.0 — vault connection test.
interface VaultStatus {
  configured: boolean
  vault_path: string
  exists: boolean
  personas: { dir: string, count: number }
  agents: { dir: string, count: number }
}
const vaultStatus = ref<VaultStatus | null>(null)
const testingVault = ref(false)

async function testVault() {
  testingVault.value = true
  try {
    // Save first so the backend reads the current value
    if (profileDraft.value.vaultPath !== profile.value?.vaultPath) {
      await $fetch(`${apiBase}/api/profile`, {
        method: 'POST',
        body: { vaultPath: profileDraft.value.vaultPath }
      })
    }
    vaultStatus.value = await $fetch<VaultStatus>(`${apiBase}/api/settings/vault`)
    toast.add({
      title: vaultStatus.value.exists ? 'Vault reachable' : 'Vault not found',
      description: vaultStatus.value.vault_path || 'Set a path first',
      color: vaultStatus.value.exists ? 'success' : 'warning',
      icon: vaultStatus.value.exists ? 'i-lucide-check-circle' : 'i-lucide-alert-circle'
    })
  } catch (err) {
    toast.add({
      title: 'Test failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    testingVault.value = false
  }
}

async function saveProfile() {
  savingProfile.value = true
  try {
    await $fetch<ProfileResponse>(`${apiBase}/api/profile`, {
      method: 'POST',
      body: profileDraft.value
    })
    await refreshProfile()
    toast.add({
      title: 'Profile saved',
      description: 'Settings written to ~/.arkaos/profile.json',
      color: 'success'
    })
  } catch (err) {
    toast.add({
      title: 'Save failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    savingProfile.value = false
  }
}

const languageOptions = [
  { label: 'English', value: 'en' },
  { label: 'Português', value: 'pt' }
]

const roleOptions = [
  { label: 'Founder', value: 'founder' },
  { label: 'CTO', value: 'cto' },
  { label: 'CEO', value: 'ceo' },
  { label: 'Engineer', value: 'engineer' },
  { label: 'Designer', value: 'designer' },
  { label: 'Operator', value: 'operator' },
  { label: 'Consultant', value: 'consultant' }
]

// ─── API Keys (preserved from earlier) ──────────────────────────────────

interface KeyRow {
  key: string
  provider: string
  configured: boolean
  used_for?: string
  masked_value: string
}

const {
  data: keysData,
  status: keysStatus,
  refresh: refreshKeys
} = fetchApi<{ keys: KeyRow[] }>('/api/keys')

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
      body: { key: keyName, value: newValue.value }
    })
    newKey.value = ''
    newValue.value = ''
    customKeyName.value = ''
    await refreshKeys()
  } catch { /* best-effort; surfaced via list refresh */ }
  saving.value = false
}

async function deleteKey(keyName: string) {
  deletingKey.value = keyName
  try {
    await $fetch(`${apiBase}/api/keys/${keyName}`, { method: 'DELETE' })
    await refreshKeys()
  } catch { /* best-effort; surfaced via list refresh */ }
  deletingKey.value = null
}

const keyOptions = [
  { label: 'OPENAI_API_KEY', value: 'OPENAI_API_KEY' },
  { label: 'FAL_API_KEY', value: 'FAL_API_KEY' },
  { label: 'GOOGLE_API_KEY', value: 'GOOGLE_API_KEY' },
  { label: 'Custom...', value: 'custom' }
]

// ─── PR63b v2.89.0 — MCPs / Hooks / Plugins / Theme sections ────────────

interface McpRow {
  name: string
  source: 'user-global' | 'arkaos-registry' | string
  transport: string
  command: string
}

interface HookCommand {
  command: string
  type: string
  timeout?: number | null
}

interface HookRow {
  hook: string
  count: number
  commands: HookCommand[]
}

interface PluginRow {
  name: string
  marketplace: string
  version: string
  scope: string
  installed_at: string
  last_updated: string
}

const { data: mcpsData, refresh: refreshMcps } = fetchApi<{ mcps: McpRow[], total: number }>('/api/settings/mcps')
const { data: hooksData, refresh: refreshHooks } = fetchApi<{
  hooks: HookRow[]
  settings_path: string
  hard_enforcement: boolean
}>('/api/settings/hooks')
const { data: pluginsData, refresh: refreshPlugins } = fetchApi<{
  plugins: PluginRow[]
  total: number
  plugins_path: string
}>('/api/settings/plugins')

const mcps = computed(() => mcpsData.value?.mcps ?? [])
const hooks = computed(() => hooksData.value?.hooks ?? [])
const plugins = computed(() => pluginsData.value?.plugins ?? [])

// Theme — Nuxt UI ships useColorMode; we just expose a picker.
const colorMode = useColorMode()
const themeOptions = [
  { label: 'System (auto)', value: 'system' },
  { label: 'Light', value: 'light' },
  { label: 'Dark', value: 'dark' }
]
const themeColor = useThemeColor()
const themeColorOptions = THEME_COLOR_OPTIONS

function transportColor(transport: string): 'primary' | 'warning' | 'success' | 'neutral' {
  if (transport === 'stdio') return 'primary'
  if (transport === 'http' || transport === 'sse') return 'success'
  return 'neutral'
}

function formatInstalledAt(iso: string): string {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso))
  } catch {
    return iso
  }
}

// ─── Section nav ────────────────────────────────────────────────────────

type SectionId = 'profile' | 'projects' | 'keys' | 'mcps' | 'hooks' | 'plugins' | 'theme' | 'updates'

const sections: { id: SectionId, label: string, icon: string }[] = [
  { id: 'profile', label: 'Profile', icon: 'i-lucide-user-circle' },
  { id: 'projects', label: 'Projects', icon: 'i-lucide-folders' },
  { id: 'keys', label: 'API Keys', icon: 'i-lucide-key' },
  { id: 'mcps', label: 'MCPs', icon: 'i-lucide-plug-2' },
  { id: 'hooks', label: 'Hooks', icon: 'i-lucide-webhook' },
  { id: 'plugins', label: 'Plugins', icon: 'i-lucide-puzzle' },
  { id: 'theme', label: 'Theme', icon: 'i-lucide-palette' },
  { id: 'updates', label: 'Updates', icon: 'i-lucide-download' }
]

const activeSection = ref<SectionId>('profile')

// ─── Updates (v3.72.0) — version check + one-click core update ──────────
const ver = ref<{ current: string, latest: string | null, update_available: boolean } | null>(null)
const checkingVer = ref(false)
const updating = ref(false)
const updateResult = ref<{ ok: boolean, output: string } | null>(null)

async function checkVersion() {
  checkingVer.value = true
  try {
    ver.value = await $fetch(`${apiBase}/api/system/version`)
  } catch {
    ver.value = null
  } finally {
    checkingVer.value = false
  }
}

async function runUpdate() {
  updating.value = true
  updateResult.value = null
  try {
    updateResult.value = await $fetch(`${apiBase}/api/system/update`, { method: 'POST' })
  } catch (e) {
    updateResult.value = { ok: false, output: e instanceof Error ? e.message : String(e) }
  } finally {
    updating.value = false
    checkVersion()
  }
}

onMounted(checkVersion)
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
            8 sections. Profile + Projects edit data; Updates runs the core
            update; everything else is read-only diagnostics.
          </p>
        </nav>

        <!-- Section content -->
        <div>
          <!-- Profile -->
          <section v-if="activeSection === 'profile'">
            <h2 class="text-lg font-semibold mb-1">
              Profile
            </h2>
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
                    help="Where your Obsidian vault lives. Used by the KB-first hook + Persona/Agent exporters."
                  >
                    <template #hint>
                      <UButton
                        label="Test connection"
                        icon="i-lucide-plug-zap"
                        size="xs"
                        variant="soft"
                        :loading="testingVault"
                        @click="testVault"
                      />
                    </template>
                    <UInput
                      v-model="profileDraft.vaultPath"
                      placeholder="/Users/you/Documents/Vault"
                      class="w-full font-mono text-sm"
                    />
                  </UFormField>

                  <!-- PR89c v3.29.0 — vault connection test result -->
                  <div
                    v-if="vaultStatus"
                    class="rounded-lg border p-3 text-xs space-y-1"
                    :class="
                      vaultStatus.exists
                        ? 'border-emerald-500/40 bg-emerald-500/5'
                        : 'border-yellow-500/40 bg-yellow-500/5'
                    "
                  >
                    <div class="flex items-center gap-2 font-semibold">
                      <UIcon
                        :name="vaultStatus.exists ? 'i-lucide-check-circle' : 'i-lucide-alert-circle'"
                        :class="vaultStatus.exists ? 'text-emerald-500 size-4' : 'text-yellow-500 size-4'"
                      />
                      <span v-if="!vaultStatus.configured">Vault not configured</span>
                      <span v-else-if="!vaultStatus.exists">Path does not exist</span>
                      <span v-else>Vault reachable</span>
                    </div>
                    <p v-if="vaultStatus.exists" class="text-muted font-mono">
                      {{ vaultStatus.vault_path }}
                    </p>
                    <ul v-if="vaultStatus.exists" class="space-y-0.5 pt-1">
                      <li class="flex items-center gap-2">
                        <UIcon name="i-lucide-folder" class="size-3 text-muted" />
                        <span class="font-mono">Personas/</span>
                        <UBadge
                          :label="`${vaultStatus.personas.count} files`"
                          variant="subtle"
                          size="xs"
                        />
                      </li>
                      <li class="flex items-center gap-2">
                        <UIcon name="i-lucide-folder" class="size-3 text-muted" />
                        <span class="font-mono">Agents/</span>
                        <UBadge
                          :label="`${vaultStatus.agents.count} files`"
                          variant="subtle"
                          size="xs"
                        />
                      </li>
                    </ul>
                  </div>

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
            <h2 class="text-lg font-semibold mb-1">
              Project directories
            </h2>
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
            <h2 class="text-lg font-semibold mb-1">
              API Keys
            </h2>
            <p class="text-sm text-muted mb-6">
              Configure API keys for external services. Keys are stored
              locally at <code class="font-mono text-xs">~/.arkaos/keys.json</code>.
            </p>

            <UCard class="mb-6">
              <div class="space-y-4">
                <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                  Add API Key
                </p>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                  <div>
                    <label class="text-xs text-muted mb-1 block">Provider</label>
                    <USelect
                      v-model="newKey"
                      :items="keyOptions"
                      class="w-full"
                      placeholder="Select key..."
                    />
                  </div>
                  <div v-if="isCustom">
                    <label class="text-xs text-muted mb-1 block">Key Name</label>
                    <UInput v-model="customKeyName" class="w-full" placeholder="MY_CUSTOM_KEY" />
                  </div>
                  <div :class="isCustom ? '' : 'md:col-span-1'">
                    <label class="text-xs text-muted mb-1 block">Value</label>
                    <UInput
                      v-model="newValue"
                      type="password"
                      class="w-full"
                      placeholder="sk-..."
                    />
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
                      <UBadge
                        v-else
                        label="Not Set"
                        color="neutral"
                        variant="outline"
                        size="xs"
                      />
                    </div>
                    <p v-if="k.used_for" class="text-xs text-muted mt-0.5">
                      {{ k.used_for }}
                    </p>
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

          <!-- MCPs -->
          <section v-else-if="activeSection === 'mcps'">
            <div class="flex items-baseline justify-between mb-1">
              <h2 class="text-lg font-semibold">
                MCPs
              </h2>
              <UButton
                label="Refresh"
                variant="ghost"
                icon="i-lucide-refresh-cw"
                size="xs"
                @click="refreshMcps()"
              />
            </div>
            <p class="text-sm text-muted mb-6">
              MCP servers configured globally for your Claude Code account.
              Sourced from <code class="font-mono text-xs">~/.claude.json</code>
              and the ArkaOS registry. Read-only.
            </p>
            <div v-if="!mcps.length" class="rounded-lg border border-default p-6 text-center">
              <UIcon name="i-lucide-plug-2" class="size-10 text-muted mx-auto mb-2" />
              <p class="text-sm text-muted">
                No MCP servers configured.
              </p>
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="m in mcps"
                :key="`${m.source}:${m.name}`"
                class="flex items-center gap-3 rounded-lg border border-default p-3"
              >
                <UIcon name="i-lucide-plug-2" class="size-4 text-muted shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-0.5">
                    <span class="text-sm font-mono font-medium">{{ m.name }}</span>
                    <UBadge :label="m.source" variant="outline" size="xs" />
                    <UBadge
                      :label="m.transport"
                      :color="transportColor(m.transport)"
                      variant="subtle"
                      size="xs"
                    />
                  </div>
                  <p v-if="m.command" class="text-xs font-mono text-muted truncate" :title="m.command">
                    {{ m.command }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- Hooks -->
          <section v-else-if="activeSection === 'hooks'">
            <div class="flex items-baseline justify-between mb-1">
              <h2 class="text-lg font-semibold">
                Hooks
              </h2>
              <UButton
                label="Refresh"
                variant="ghost"
                icon="i-lucide-refresh-cw"
                size="xs"
                @click="refreshHooks()"
              />
            </div>
            <p class="text-sm text-muted mb-6">
              Claude Code hooks wired by the ArkaOS installer.
              Sourced from
              <code class="font-mono text-xs">{{ hooksData?.settings_path ?? '~/.claude/settings.json' }}</code>.
              Read-only — re-wire via <code class="font-mono text-xs">npx arkaos@latest update</code>.
            </p>
            <div
              v-if="hooksData?.hard_enforcement"
              class="mb-4 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm"
            >
              <UIcon name="i-lucide-shield-check" class="size-4 inline text-primary mr-1" />
              Hard enforcement is <strong>ON</strong>. Effect tools require
              <code class="font-mono text-xs">[arka:routing]</code> markers.
            </div>
            <div v-if="!hooks.length" class="rounded-lg border border-default p-6 text-center">
              <UIcon name="i-lucide-webhook" class="size-10 text-muted mx-auto mb-2" />
              <p class="text-sm text-muted">
                No hooks wired in settings.json.
              </p>
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="h in hooks"
                :key="h.hook"
                class="rounded-lg border border-default p-3"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-sm font-mono font-semibold">{{ h.hook }}</span>
                  <UBadge :label="`${h.count}`" variant="subtle" size="xs" />
                </div>
                <ul class="space-y-1">
                  <li
                    v-for="(c, idx) in h.commands"
                    :key="idx"
                    class="flex items-center gap-2 text-xs"
                  >
                    <UIcon name="i-lucide-terminal" class="size-3 text-muted shrink-0" />
                    <code class="font-mono text-xs truncate flex-1" :title="c.command">
                      {{ c.command }}
                    </code>
                    <span v-if="c.timeout" class="text-muted whitespace-nowrap">
                      {{ c.timeout }}s
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </section>

          <!-- Plugins -->
          <section v-else-if="activeSection === 'plugins'">
            <div class="flex items-baseline justify-between mb-1">
              <h2 class="text-lg font-semibold">
                Plugins
              </h2>
              <UButton
                label="Refresh"
                variant="ghost"
                icon="i-lucide-refresh-cw"
                size="xs"
                @click="refreshPlugins()"
              />
            </div>
            <p class="text-sm text-muted mb-6">
              Claude Code plugins installed via the marketplace system
              (PR43 auto-install + PR55 ArkaOS marketplace). Sourced
              from <code class="font-mono text-xs">{{ pluginsData?.plugins_path ?? '~/.claude/plugins/installed_plugins.json' }}</code>.
            </p>
            <div v-if="!plugins.length" class="rounded-lg border border-default p-6 text-center">
              <UIcon name="i-lucide-puzzle" class="size-10 text-muted mx-auto mb-2" />
              <p class="text-sm text-muted">
                No plugins installed.
              </p>
              <p class="text-xs text-muted mt-2">
                Try <code class="font-mono">/plugin marketplace add andreagroferreira/arka-os</code>
                from Claude Code.
              </p>
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="p in plugins"
                :key="`${p.marketplace}:${p.name}:${p.version}`"
                class="flex items-center gap-3 rounded-lg border border-default p-3"
              >
                <UIcon name="i-lucide-puzzle" class="size-4 text-muted shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-0.5">
                    <span class="text-sm font-semibold">{{ p.name }}</span>
                    <UBadge :label="p.marketplace" variant="outline" size="xs" />
                    <UBadge
                      v-if="p.scope"
                      :label="p.scope"
                      variant="soft"
                      size="xs"
                    />
                    <UBadge
                      v-if="p.version"
                      :label="`v${p.version}`"
                      variant="subtle"
                      size="xs"
                    />
                  </div>
                  <p v-if="p.installed_at" class="text-xs text-muted">
                    Installed {{ formatInstalledAt(p.installed_at) }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- Theme -->
          <section v-else-if="activeSection === 'theme'">
            <h2 class="text-lg font-semibold mb-1">
              Theme
            </h2>
            <p class="text-sm text-muted mb-6">
              Light / dark / system (follows OS preference).
              Stored locally by your browser.
            </p>
            <UCard>
              <div class="space-y-4">
                <UFormField label="Appearance">
                  <USelect
                    v-model="colorMode.preference"
                    :items="themeOptions"
                    class="w-full max-w-xs"
                  />
                </UFormField>
                <p class="text-xs text-muted">
                  Currently rendering as
                  <UBadge :label="colorMode.value" variant="subtle" size="xs" />
                </p>

                <!-- PR92d v3.42.0 — primary color picker -->
                <UFormField label="Primary color" help="Tints buttons, badges, links across the dashboard.">
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="opt in themeColorOptions"
                      :key="opt.value"
                      type="button"
                      class="rounded-lg border p-2 transition-colors text-xs flex items-center gap-2"
                      :class="themeColor.current.value === opt.value
                        ? 'border-primary bg-primary/10 font-semibold'
                        : 'border-default hover:border-primary/40'"
                      @click="themeColor.setAndPersist(opt.value)"
                    >
                      <span
                        class="size-4 rounded-full"
                        :class="{
                          'bg-emerald-500': opt.value === 'emerald',
                          'bg-blue-500': opt.value === 'blue',
                          'bg-indigo-500': opt.value === 'indigo',
                          'bg-violet-500': opt.value === 'violet',
                          'bg-rose-500': opt.value === 'rose',
                          'bg-amber-500': opt.value === 'amber',
                          'bg-teal-500': opt.value === 'teal',
                          'bg-cyan-500': opt.value === 'cyan'
                        }"
                      />
                      {{ opt.label }}
                    </button>
                  </div>
                </UFormField>
              </div>
            </UCard>
          </section>

          <section v-else-if="activeSection === 'updates'">
            <h2 class="text-lg font-semibold mb-1">
              Updates
            </h2>
            <p class="text-sm text-muted mb-6">
              Keep ArkaOS current. The button runs the core update
              (<code class="text-xs">npx arkaos@latest update</code>); finish
              the project sync by running <code class="text-xs">/arka update</code>
              in Claude Code.
            </p>
            <UCard>
              <div class="space-y-4">
                <div class="flex items-center gap-3 flex-wrap">
                  <div class="text-sm">
                    Installed:
                    <UBadge :label="`v${ver?.current ?? '—'}`" variant="subtle" size="sm" />
                  </div>
                  <div class="text-sm">
                    Latest:
                    <UBadge
                      :label="ver?.latest ? `v${ver.latest}` : '—'"
                      :color="ver?.update_available ? 'warning' : 'success'"
                      variant="subtle"
                      size="sm"
                    />
                  </div>
                  <UButton
                    size="xs"
                    variant="ghost"
                    icon="i-lucide-refresh-cw"
                    :loading="checkingVer"
                    @click="checkVersion"
                  >
                    Check
                  </UButton>
                </div>

                <div v-if="ver?.update_available" class="flex items-center gap-3">
                  <UButton
                    icon="i-lucide-download"
                    color="primary"
                    :loading="updating"
                    @click="runUpdate"
                  >
                    {{ updating ? 'Updating…' : `Update to v${ver.latest}` }}
                  </UButton>
                  <span class="text-xs text-muted">Runs the core update, then asks you to finish in Claude Code.</span>
                </div>
                <p v-else-if="ver && !ver.update_available" class="text-sm text-success flex items-center gap-1.5">
                  <UIcon name="i-lucide-check-circle" class="size-4" />
                  You're on the latest version.
                </p>
                <p v-else class="text-sm text-muted">
                  Couldn't reach the version service.
                </p>

                <div
                  v-if="updateResult"
                  class="rounded-lg border p-3 text-xs"
                  :class="updateResult.ok ? 'border-success/40 bg-success/5' : 'border-error/40 bg-error/5'"
                >
                  <div class="flex items-center gap-1.5 font-medium mb-1">
                    <UIcon :name="updateResult.ok ? 'i-lucide-check-circle' : 'i-lucide-alert-triangle'" class="size-4" />
                    {{ updateResult.ok ? 'Core updated' : 'Update failed' }}
                  </div>
                  <p v-if="updateResult.ok" class="text-muted">
                    Now run <code>/arka update</code> in Claude Code to sync all projects (step 2).
                  </p>
                  <pre class="mt-2 whitespace-pre-wrap font-mono text-[11px] text-muted max-h-48 overflow-y-auto">{{ updateResult.output }}</pre>
                </div>
              </div>
            </UCard>
          </section>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
