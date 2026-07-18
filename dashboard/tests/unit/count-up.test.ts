import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useCountUp } from '../../app/composables/useCountUp'

function mockMatchMedia(reduced: boolean) {
  vi.stubGlobal('matchMedia', () => ({
    matches: reduced,
    media: '',
    addEventListener: () => {},
    removeEventListener: () => {}
  }))
}

describe('useCountUp', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('jumps straight to the target under reduced motion', () => {
    mockMatchMedia(true)
    const target = ref(120)
    const { display } = useCountUp(target, 900)

    expect(display.value).toBe(120)
  })

  it('jumps straight to the target when duration is zero', () => {
    mockMatchMedia(false)
    const target = ref(75)
    const { display } = useCountUp(target, 0)

    expect(display.value).toBe(75)
  })

  it('jumps straight to a non-finite target instead of animating NaN', () => {
    mockMatchMedia(false)
    const target = ref(Number.POSITIVE_INFINITY)
    const { display } = useCountUp(target, 900)

    expect(display.value).toBe(Number.POSITIVE_INFINITY)
  })

  it('animates to the target and lands exactly on it', () => {
    mockMatchMedia(false)
    const target = ref(100)

    let now = 0
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      frames.push(cb)
      return frames.length
    })
    vi.stubGlobal('cancelAnimationFrame', () => {})

    const { display } = useCountUp(target, 1000)
    expect(display.value).toBe(0)

    // Drive the first frame at t=500ms — cubic ease-out, ~0.875 progress.
    now = 500
    frames.shift()?.(500)
    expect(display.value).toBeGreaterThan(50)
    expect(display.value).toBeLessThan(100)

    // Drive the final frame at t=1000ms — must land exactly on target.
    now = 1000
    frames.shift()?.(1000)
    expect(display.value).toBe(100)
  })
})
