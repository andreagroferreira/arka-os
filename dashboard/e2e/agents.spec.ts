import { test, expect, type Page } from '@playwright/test'

// Agents page (critical path #1). Drives real data from the dashboard API
// (/api/agents backed by knowledge/agents-registry-v2.json) — same
// prerequisites as terminal.spec.ts: dashboard-api on :3334 + nuxt on :3000.

function collectErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', err => errors.push(err.message))
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
  })
  return errors
}

test.describe('agents page', () => {
  test('renders the real agent roster from the registry', async ({ page }) => {
    const errors = collectErrors(page)

    await page.goto('/agents')
    await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible()

    // Real rows from the registry, not template placeholders.
    const rows = page.locator('tbody tr')
    await expect.poll(() => rows.count(), { timeout: 15_000 }).toBeGreaterThan(10)
    await expect(page.locator('tbody')).not.toContainText('Alex Smith')

    expect(errors, `console/page errors: ${errors.join(' | ')}`).toEqual([])
  })

  test('search narrows the roster to a known agent', async ({ page }) => {
    await page.goto('/agents')
    const search = page.getByLabel('Search agents by name, role, or department')
    await expect(search).toBeVisible()

    await search.fill('Marta')
    const rows = page.locator('tbody tr')
    await expect.poll(() => rows.count()).toBeGreaterThan(0)
    await expect(rows.first()).toContainText('Marta')
  })
})
