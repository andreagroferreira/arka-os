import { describe, expect, it } from 'vitest'
import { randomFrom, randomInt } from '../../app/utils'

describe('randomInt', () => {
  it('stays inside the inclusive range', () => {
    for (let i = 0; i < 500; i++) {
      const n = randomInt(3, 7)
      expect(n).toBeGreaterThanOrEqual(3)
      expect(n).toBeLessThanOrEqual(7)
      expect(Number.isInteger(n)).toBe(true)
    }
  })

  it('handles a single-value range', () => {
    expect(randomInt(4, 4)).toBe(4)
  })
})

describe('randomFrom', () => {
  it('returns a member of the array', () => {
    const items = ['a', 'b', 'c'] as const
    for (let i = 0; i < 100; i++) {
      expect(items).toContain(randomFrom([...items]))
    }
  })

  it('returns the only element of a singleton', () => {
    expect(randomFrom([42])).toBe(42)
  })
})
