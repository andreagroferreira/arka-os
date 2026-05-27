import { defineConfig, devices } from '@playwright/test'

// E2E for the persistent terminal (v3.71.0). These tests drive a real
// browser against BOTH running servers — they are NOT part of the default
// unit run. Prerequisites:
//   1. Dashboard API:  python scripts/dashboard-api.py   (http://localhost:3334)
//   2. Nuxt dev:       npm run dev                        (http://localhost:3000)
//   3. One-time:       npx playwright install chromium
// Run:                 npm run test:e2e
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry'
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } }
  ]
})
