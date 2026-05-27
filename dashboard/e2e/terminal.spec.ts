import { test, expect, type Page } from '@playwright/test'

// Persistent terminal (v3.71.0). Codifies the two invariants verified
// manually on ship: navigation keeps the same session, and a full reload
// reattaches to the same backend PTY with its scrollback replayed — no
// duplicate session in either case.

function persistedSessionId(page: Page): Promise<string | null> {
  return page.evaluate(() => {
    const raw = localStorage.getItem('arka-terminal-tabs')
    const tabs = raw ? JSON.parse(raw) : []
    return tabs[0]?.sessionId ?? null
  })
}

const tabCount = (page: Page) =>
  page.locator('button[aria-label^="Close Session"]').count()

test.describe('persistent terminal', () => {
  test('session survives in-app navigation', async ({ page }) => {
    await page.goto('/terminal')
    await expect(page.locator('.xterm')).toBeVisible()
    await expect.poll(() => persistedSessionId(page)).not.toBeNull()
    const before = await persistedSessionId(page)

    // Navigate away — the dock lives in the layout, so it must persist.
    await page.click('a[href="/budget"]')
    await expect(page).toHaveURL(/\/budget/)
    await expect(page.locator('section[aria-label="Terminal dock"]')).toBeAttached()

    // ...and back: same single session, not a fresh spawn.
    await page.click('a[href="/terminal"]')
    await expect(page).toHaveURL(/\/terminal/)
    expect(await tabCount(page)).toBe(1)
    expect(await persistedSessionId(page)).toBe(before)
  })

  test('session reattaches with scrollback after a full reload', async ({ page }) => {
    await page.goto('/terminal')
    await expect(page.locator('.xterm')).toBeVisible()
    await expect.poll(() => persistedSessionId(page)).not.toBeNull()

    const marker = `ARKA_E2E_${Date.now()}`
    await page.locator('.xterm-screen').click()
    await page.locator('.xterm-helper-textarea').pressSequentially(`echo ${marker}`)
    await page.locator('.xterm-helper-textarea').press('Enter')
    await expect(page.locator('.xterm-rows')).toContainText(marker)
    const before = await persistedSessionId(page)

    await page.reload()

    // Reattach: same session id, single tab, scrollback replayed by the
    // backend ring-buffer.
    await expect.poll(() => tabCount(page)).toBe(1)
    expect(await persistedSessionId(page)).toBe(before)
    await expect(page.locator('.xterm-rows')).toContainText(marker)
  })
})
