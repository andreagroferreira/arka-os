import { test, expect, type Page } from '@playwright/test'

// Models page (critical path #3). Renders the Model Fabric role routing
// from /api/models — same prerequisites as terminal.spec.ts.

function collectErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', err => errors.push(err.message))
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
  })
  return errors
}

test.describe('models page', () => {
  test('renders role routing and usage controls from live data', async ({ page }) => {
    const errors = collectErrors(page)

    await page.goto('/models')
    await expect(page.getByRole('heading', { name: 'Models' })).toBeVisible()

    // At least one role row with its inline edit control — real routing data.
    await expect
      .poll(() => page.locator('button[aria-label$="routing"]').count(), { timeout: 15_000 })
      .toBeGreaterThan(0)
    await expect(page.getByLabel('Usage period')).toBeVisible()

    expect(errors, `console/page errors: ${errors.join(' | ')}`).toEqual([])
  })
})
