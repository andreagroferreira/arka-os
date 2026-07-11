// Self-contained /ws/tasks subscription (additive — tasks.vue and
// PersonaWizard keep their own connections). Emits normalized events;
// silently stays closed on failure so poll-based consumers degrade clean.
export interface TaskStreamEvent {
  type: 'job_progress' | 'job_complete' | 'job_failed' | 'job_cancelled'
  job_id: string
  message?: string
  progress?: number
  error?: string
  ts: number
}

export function useTaskStream(onEvent: (e: TaskStreamEvent) => void) {
  const { apiBase } = useApi()
  let ws: WebSocket | null = null

  onMounted(() => {
    try {
      ws = new WebSocket(`${apiBase.replace(/^http/, 'ws')}/ws/tasks`)
      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data)
          if (typeof data?.type === 'string' && data.type.startsWith('job_')) {
            onEvent({ ...data, ts: Date.now() })
          }
        } catch {
          // non-JSON frame — ignore
        }
      }
    } catch {
      ws = null
    }
  })

  onUnmounted(() => {
    ws?.close()
    ws = null
  })
}
