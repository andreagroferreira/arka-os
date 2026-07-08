import { test, expect, type Page } from '@playwright/test'

// Knowledge page (critical path #2). Loads live stats from
// /api/knowledge/stats — same prerequisites as terminal.spec.ts.

function collectErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', err => errors.push(err.message))
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
  })
  return errors
}

test.describe('knowledge page', () => {
  test('loads live stats and the search surface', async ({ page }) => {
    const errors = collectErrors(page)

    await page.goto('/knowledge')
    await expect(page.getByRole('heading', { name: 'Knowledge Base' })).toBeVisible()

    // The stats fetch resolved: the search input only renders with data.
    await expect(page.getByLabel('Search knowledge base')).toBeVisible({ timeout: 15_000 })

    expect(errors, `console/page errors: ${errors.join(' | ')}`).toEqual([])
  })
})
