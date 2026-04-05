<script setup lang="ts">
interface Task {
  id: string
  title: string
  type: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  department: string
  progress: number
}

const { fetchApi } = useApi()

const { data: tasks, pending, error, refresh } = await fetchApi<Task[]>('/api/tasks')

const activeTasks = computed(() =>
  tasks.value?.filter((t) => t.status === 'processing') ?? [],
)

const allTasks = computed(() => tasks.value ?? [])

function statusColor(status: string): 'success' | 'info' | 'neutral' | 'error' {
  const map: Record<string, 'success' | 'info' | 'neutral' | 'error'> = {
    completed: 'success',
    processing: 'info',
    queued: 'neutral',
    failed: 'error',
  }
  return map[status] ?? 'neutral'
}

function progressColor(status: string): 'success' | 'info' | 'neutral' | 'error' {
  return statusColor(status)
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-white">
        Tasks
      </h2>
      <UButton
        color="primary"
        variant="soft"
        size="sm"
        :loading="pending"
        @click="refresh()"
      >
        Refresh
      </UButton>
    </div>

    <!-- Loading -->
    <UCard v-if="pending">
      <div class="animate-pulse space-y-3 py-8">
        <div v-for="i in 5" :key="i" class="h-10 bg-gray-800 rounded" />
      </div>
    </UCard>

    <!-- Error -->
    <UCard v-else-if="error">
      <div role="alert" class="text-center py-8">
        <p class="text-red-400 font-medium mb-2">
          Failed to load tasks
        </p>
        <UButton color="primary" variant="soft" @click="refresh()">
          Retry
        </UButton>
      </div>
    </UCard>

    <!-- Empty -->
    <div v-else-if="!allTasks.length" class="text-center py-12">
      <p class="text-gray-500">
        No tasks in the system.
      </p>
    </div>

    <template v-else>
      <!-- Active tasks with progress -->
      <div v-if="activeTasks.length" class="mb-8">
        <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Active ({{ activeTasks.length }})
        </h3>
        <div class="space-y-3">
          <UCard v-for="task in activeTasks" :key="task.id">
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <span class="text-sm font-medium text-white">{{ task.title }}</span>
                  <UBadge color="neutral" variant="subtle" size="sm">
                    {{ task.department }}
                  </UBadge>
                </div>
                <span class="text-sm text-gray-400">{{ task.progress }}%</span>
              </div>
              <UProgress :value="task.progress" color="info" size="sm" />
            </div>
          </UCard>
        </div>
      </div>

      <!-- All tasks table -->
      <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
        All Tasks ({{ allTasks.length }})
      </h3>

      <!-- Header -->
      <div class="hidden md:grid grid-cols-12 gap-4 px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        <span class="col-span-1">ID</span>
        <span class="col-span-3">Title</span>
        <span class="col-span-2">Type</span>
        <span class="col-span-2">Status</span>
        <span class="col-span-2">Department</span>
        <span class="col-span-2">Progress</span>
      </div>

      <div class="space-y-1">
        <UCard v-for="task in allTasks" :key="task.id">
          <div class="grid grid-cols-2 md:grid-cols-12 gap-2 md:gap-4 items-center">
            <div class="col-span-1">
              <span class="text-xs font-mono text-gray-500">{{ task.id }}</span>
            </div>
            <div class="col-span-3">
              <span class="text-sm text-white">{{ task.title }}</span>
            </div>
            <div class="col-span-2">
              <span class="text-sm text-gray-400">{{ task.type }}</span>
            </div>
            <div class="col-span-2">
              <UBadge :color="statusColor(task.status)" variant="subtle" size="sm">
                {{ task.status }}
              </UBadge>
            </div>
            <div class="col-span-2">
              <span class="text-sm text-gray-400">{{ task.department }}</span>
            </div>
            <div class="col-span-2">
              <UProgress
                :value="task.progress"
                :color="progressColor(task.status)"
                size="xs"
              />
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </div>
</template>
