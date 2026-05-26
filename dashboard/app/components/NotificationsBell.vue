<script setup lang="ts">
// PR93d v3.46.0 — bell-icon notifications popover.

const feed = useActivityFeed()
onMounted(() => feed.load())

function formatRelative(iso: string): string {
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return iso
  const diff = Date.now() - ts
  const m = Math.floor(diff / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function kindIcon(kind: string): string {
  return {
    success: 'i-lucide-check-circle',
    warning: 'i-lucide-alert-triangle',
    error: 'i-lucide-x-circle',
    info: 'i-lucide-info',
  }[kind] ?? 'i-lucide-circle'
}

function kindColor(kind: string): string {
  return {
    success: 'text-emerald-500',
    warning: 'text-amber-500',
    error: 'text-rose-500',
    info: 'text-blue-500',
  }[kind] ?? 'text-muted'
}
</script>

<template>
  <UPopover :ui="{ content: 'w-80' }">
    <UButton
      icon="i-lucide-bell"
      variant="ghost"
      size="sm"
      aria-label="Notifications"
      :ui="{ base: 'relative' }"
    >
      <UBadge
        v-if="feed.unreadCount.value > 0"
        :label="String(Math.min(feed.unreadCount.value, 99))"
        color="primary"
        size="xs"
        class="absolute -top-1 -right-1 min-w-4"
      />
    </UButton>

    <template #content>
      <div class="p-2 border-b border-default flex items-center justify-between gap-2">
        <div>
          <p class="text-sm font-semibold">Recent activity</p>
          <p class="text-xs text-muted">
            {{ feed.unreadCount.value }} unread ·
            {{ feed.events.value.length }} total
          </p>
        </div>
        <div class="flex items-center gap-1">
          <UButton
            v-if="feed.unreadCount.value > 0"
            label="Mark all read"
            variant="ghost"
            size="xs"
            @click="feed.markAllRead()"
          />
          <UButton
            v-if="feed.events.value.length > 0"
            label="Clear"
            variant="ghost"
            size="xs"
            @click="feed.clear()"
          />
        </div>
      </div>
      <div class="max-h-80 overflow-y-auto">
        <p
          v-if="feed.events.value.length === 0"
          class="p-6 text-center text-sm text-muted"
        >
          <UIcon name="i-lucide-bell-off" class="size-6 inline mb-1" /><br>
          Nothing here yet.
        </p>
        <ul v-else class="divide-y divide-default">
          <li
            v-for="ev in feed.events.value"
            :key="ev.id"
            class="px-3 py-2 hover:bg-elevated/40 transition-colors group cursor-pointer"
            :class="{ 'bg-primary/5': !ev.read }"
            @click="feed.markRead(ev.id)"
          >
            <component
              :is="ev.to ? 'NuxtLink' : 'div'"
              :to="ev.to"
              class="flex items-start gap-2"
            >
              <UIcon
                :name="kindIcon(ev.kind)"
                :class="['size-4 shrink-0 mt-0.5', kindColor(ev.kind)]"
              />
              <div class="flex-1 min-w-0">
                <p class="text-sm flex items-center gap-1.5">
                  <span
                    v-if="!ev.read"
                    class="inline-block size-1.5 rounded-full bg-primary shrink-0"
                    aria-label="unread"
                  />
                  <span :class="ev.read ? 'font-normal text-muted' : 'font-medium'" class="truncate">
                    {{ ev.title }}
                  </span>
                </p>
                <p v-if="ev.description" class="text-xs text-muted truncate">
                  {{ ev.description }}
                </p>
                <p class="text-xs text-muted/70 mt-0.5">{{ formatRelative(ev.ts) }}</p>
              </div>
              <UButton
                icon="i-lucide-x"
                variant="ghost"
                size="xs"
                aria-label="Dismiss"
                class="opacity-0 group-hover:opacity-100 transition-opacity"
                @click.stop.prevent="feed.remove(ev.id)"
              />
            </component>
          </li>
        </ul>
      </div>
    </template>
  </UPopover>
</template>
