// rAF count-up on the shared motion rhythm. Reduced-motion (or a zero
// duration) jumps straight to the target so numbers are never withheld.
export function useCountUp(target: Ref<number>, duration = 900) {
  const display = ref(0)
  let frame = 0

  const run = (to: number) => {
    cancelAnimationFrame(frame)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || duration <= 0 || !Number.isFinite(to)) {
      display.value = to
      return
    }
    const from = display.value
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      display.value = from + (to - from) * eased
      if (t < 1) frame = requestAnimationFrame(tick)
      else display.value = to
    }
    frame = requestAnimationFrame(tick)
  }

  watch(target, run, { immediate: true })
  onUnmounted(() => cancelAnimationFrame(frame))

  return { display }
}
