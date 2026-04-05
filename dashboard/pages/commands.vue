<script setup lang="ts">
interface Command {
  command: string
  department: string
  description: string
}

const { fetchApi } = useApi()

const { data: commands, pending, error, refresh } = await fetchApi<Command[]>('/api/commands')

const searchQuery = ref('')
const selectedDepartment = ref('')

const departments = computed(() => {
  if (!commands.value) return []
  const depts = [...new Set(commands.value.map((c) => c.department))].sort()
  return [{ label: 'All Departments', value: '' }, ...depts.map((d) => ({ label: d, value: d }))]
})

const filteredCommands = computed(() => {
  if (!commands.value) return []
  let result = commands.value

  if (selectedDepartment.value) {
    result = result.filter((c) => c.department === selectedDepartment.value)
  }

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(
      (c) =>
        c.command.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.department.toLowerCase().includes(q),
    )
  }

  return result
})

const columns = [
  { key: 'command', label: 'Command' },
  { key: 'department', label: 'Department' },
  { key: 'description', label: 'Description' },
]
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-white mb-6">
      Commands
    </h2>

    <!-- Filters -->
    <div class="flex flex-col sm:flex-row gap-4 mb-6">
      <UInput
        v-model="searchQuery"
        placeholder="Search commands..."
        class="flex-1"
        aria-label="Search commands"
      />
      <USelect
        v-model="selectedDepartment"
        :items="departments"
        placeholder="Filter by department"
        class="w-full sm:w-64"
      />
    </div>

    <!-- Loading -->
    <UCard v-if="pending">
      <div class="animate-pulse space-y-3 py-8">
        <div v-for="i in 8" :key="i" class="h-8 bg-gray-800 rounded" />
      </div>
    </UCard>

    <!-- Error -->
    <UCard v-else-if="error">
      <div role="alert" class="text-center py-8">
        <p class="text-red-400 font-medium mb-2">
          Failed to load commands
        </p>
        <UButton color="primary" variant="soft" @click="refresh()">
          Retry
        </UButton>
      </div>
    </UCard>

    <!-- Empty -->
    <div v-else-if="!filteredCommands.length" class="text-center py-12">
      <p class="text-gray-500">
        {{ searchQuery || selectedDepartment ? 'No commands match your search.' : 'No commands available.' }}
      </p>
    </div>

    <!-- Command list -->
    <div v-else class="space-y-1">
      <!-- Header -->
      <div class="hidden md:grid grid-cols-12 gap-4 px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        <span class="col-span-3">Command</span>
        <span class="col-span-2">Department</span>
        <span class="col-span-7">Description</span>
      </div>

      <!-- Rows -->
      <UCard v-for="cmd in filteredCommands" :key="cmd.command">
        <div class="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 items-start">
          <div class="col-span-3">
            <code class="text-primary-400 text-sm font-mono">{{ cmd.command }}</code>
          </div>
          <div class="col-span-2">
            <UBadge color="neutral" variant="subtle" size="sm">
              {{ cmd.department }}
            </UBadge>
          </div>
          <div class="col-span-7">
            <p class="text-sm text-gray-400">{{ cmd.description }}</p>
          </div>
        </div>
      </UCard>

      <!-- Result count -->
      <p class="text-xs text-gray-600 mt-4 px-4">
        {{ filteredCommands.length }} command{{ filteredCommands.length !== 1 ? 's' : '' }}
      </p>
    </div>
  </div>
</template>
