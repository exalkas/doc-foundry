import { test, expect } from '@playwright/test'
import { BrowserUse } from 'browser-use'

const APP_ORIGIN = process.env.APP_ORIGIN || 'http://localhost:3000'

/**
 * Helpers / fixtures
 * These assume that auth helpers and seeded users/workspaces exist in the test environment.
 * Adjust data and selectors to match the actual implementation.
 */

async function loginAsUser(page, role: 'owner' | 'member' | 'readonly' = 'owner') {
  const browserUse = new BrowserUse(page)

  const email =
    role === 'owner'
      ? 'owner@example.com'
      : role === 'member'
      ? 'member@example.com'
      : 'readonly@example.com'
  const password = 'Password123!'

  await page.goto(`${APP_ORIGIN}/login`)
  await browserUse.perform(`Fill the email field with ${email}`)
  await browserUse.perform(`Fill the password field with ${password}`)
  await browserUse.perform('Click the login submit button')
  await page.waitForURL('**/app', { waitUntil: 'networkidle' })
}

async function waitForDashboardLoaded(page) {
  await expect(page).toHaveURL(/\/app(?:\?|$|$)/)
  await expect(page.getByRole('main')).toBeVisible()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  // usage summary widget
  await expect(page.getByTestId('usage-summary')).toBeVisible()
  // quick actions
  await expect(page.getByTestId('quick-actions')).toBeVisible()
}

test.describe('Dashboard /app - navigation and overview', () => {
  test.beforeEach(async ({ page }) => {
    // Clear auth state between tests
    await page.context().clearCookies()
    await page.context().clearPermissions()
  })

  test('redirects unauthenticated visitor to login from /app', async ({ page }) => {
    await page.goto(`${APP_ORIGIN}/app`)
    await page.waitForURL('**/login')
    await expect(page.getByRole('heading', { name: /login/i })).toBeVisible()
  })

  test('loads dashboard for authenticated owner and shows key widgets', async ({ page }) => {
    await loginAsUser(page, 'owner')
    await waitForDashboardLoaded(page)

    // Header / branding
    await expect(page.getByTestId('app-header')).toBeVisible()
    await expect(page.getByTestId('workspace-switcher')).toBeVisible()
    await expect(page.getByTestId('branding-logo')).toBeVisible()
    await expect(page.getByTestId('user-menu-trigger')).toBeVisible()

    // Usage summary content
    const usage = page.getByTestId('usage-summary')
    await expect(usage.getByText(/current plan/i)).toBeVisible()
    await expect(usage.getByText(/documents processed/i)).toBeVisible()
    await expect(usage.getByText(/pages processed/i)).toBeVisible()
    await expect(usage.getByTestId('plan-limit-indicator')).toBeVisible()

    // Recent projects list
    const recentProjects = page.getByTestId('recent-projects')
    await expect(recentProjects).toBeVisible()
    await expect(recentProjects.getByRole('heading', { name: /recent projects/i })).toBeVisible()

    // Latest extractions list
    const latestExtractions = page.getByTestId('latest-extractions')
    await expect(latestExtractions).toBeVisible()
    await expect(
      latestExtractions.getByRole('heading', { name: /latest extractions/i })
    ).toBeVisible()

    // Quick actions
    const quickActions = page.getByTestId('quick-actions')
    await expect(quickActions.getByRole('button', { name: /upload document/i })).toBeVisible()
    await expect(quickActions.getByRole('button', { name: /create template/i })).toBeVisible()
    await expect(quickActions.getByRole('button', { name: /view api keys/i })).toBeVisible()
  })

  test('workspace switcher changes workspace and updates branding + data', async ({ page }) => {
    await loginAsUser(page, 'owner')
    await waitForDashboardLoaded(page)

    const header = page.getByTestId('app-header')
    const switcher = header.getByTestId('workspace-switcher')

    await switcher.click()
    await expect(page.getByRole('menu')).toBeVisible()

    // Assume there is at least a second workspace seeded as "Acme Logistics"
    const newWorkspaceOption = page.getByRole('menuitem', { name: /acme logistics/i })
    await expect(newWorkspaceOption).toBeVisible()
    await newWorkspaceOption.click()

    // After switching, dashboard should reload /app with new workspace
    await page.waitForURL('**/app', { waitUntil: 'networkidle' })

    // Branding logo/primary color changed (simplified check via data attribute or text)
    await expect(page.getByTestId('current-workspace-name')).toHaveText(/acme logistics/i)

    // Usage summary should reload and show some value (basic sanity check)
    await expect(page.getByTestId('usage-summary')).toBeVisible()
  })

  test('quick action: "Upload document" from dashboard navigates to /app/upload', async ({
    page,
  }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const quickActions = page.getByTestId('quick-actions')
    await quickActions.getByRole('button', { name: /upload document/i }).click()

    await page.waitForURL('**/app/upload')
    await expect(page.getByRole('heading', { name: /upload document/i })).toBeVisible()
    await expect(page.getByTestId('upload-form')).toBeVisible()
  })

  test('quick action: "Create template" from dashboard navigates to templates list or editor', async ({
    page,
  }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const quickActions = page.getByTestId('quick-actions')
    await quickActions.getByRole('button', { name: /create template/i }).click()

    await page.waitForURL(/\/app\/templates/)
    await expect(page.getByRole('heading', { name: /templates/i })).toBeVisible()
  })

  test('quick action: "View API Keys" navigates to /app/settings/api-keys', async ({ page }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const quickActions = page.getByTestId('quick-actions')
    await quickActions.getByRole('button', { name: /view api keys/i }).click()

    await page.waitForURL('**/app/settings/api-keys')
    await expect(page.getByRole('heading', { name: /api key management/i })).toBeVisible()
    await expect(page.getByTestId('api-keys-table')).toBeVisible()
  })

  test('recent projects: clicking project navigates to project detail', async ({ page }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const recentProjects = page.getByTestId('recent-projects')
    const firstProject = recentProjects.getByRole('link').first()
    const projectName = await firstProject.textContent()

    await firstProject.click()
    await page.waitForURL(/\/app\/projects\//)

    await expect(page.getByRole('heading', { level: 1 })).toContainText(projectName || '')
    await expect(page.getByTestId('project-tabs')).toBeVisible()
  })

  test('latest extractions: clicking document row navigates to extraction preview', async ({
    page,
  }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const latestExtractions = page.getByTestId('latest-extractions')

    // If there are no extractions, the UI should show an empty-state message
    const emptyState = latestExtractions.getByText(/no extractions yet/i)
    if (await emptyState.isVisible().catch(() => false)) {
      await expect(emptyState).toBeVisible()
      return
    }

    const firstDocLink = latestExtractions.getByRole('link').first()
    await firstDocLink.click()

    await page.waitForURL(/\/app\/documents\//)
    await expect(page.getByTestId('extraction-tabs')).toBeVisible()
    await expect(page.getByTestId('document-info')).toBeVisible()
  })

  test('dashboard shows empty states when no projects or extractions exist', async ({ page }) => {
    // Assume this readonly user has a fresh workspace with no projects/docs
    await loginAsUser(page, 'readonly')
    await waitForDashboardLoaded(page)

    const recentProjects = page.getByTestId('recent-projects')
    await expect(recentProjects.getByText(/no projects yet/i)).toBeVisible()
    await expect(
      recentProjects.getByRole('link', { name: /create your first project/i })
    ).toBeVisible()

    const latestExtractions = page.getByTestId('latest-extractions')
    await expect(latestExtractions.getByText(/no extractions yet/i)).toBeVisible()
  })

  test('role-based visibility: readonly user cannot see upload/create actions', async ({ page }) => {
    await loginAsUser(page, 'readonly')
    await waitForDashboardLoaded(page)

    const quickActions = page.getByTestId('quick-actions')
    await expect(
      quickActions.getByRole('button', { name: /upload document/i })
    ).not.toBeVisible({ timeout: 1000 })
    await expect(
      quickActions.getByRole('button', { name: /create template/i })
    ).not.toBeVisible({ timeout: 1000 })
    // readonly should still see "View API Keys" only if allowed; by spec readonly can't manage apikeys
    await expect(
      quickActions.getByRole('button', { name: /view api keys/i })
    ).not.toBeVisible({ timeout: 1000 })
  })

  test('usage summary reflects approaching limit with visual indicator', async ({ page }) => {
    // Assume owner workspace is seeded with usage near 80% threshold
    await loginAsUser(page, 'owner')
    await waitForDashboardLoaded(page)

    const usage = page.getByTestId('usage-summary')
    await expect(usage).toBeVisible()

    // Check indicator style or warning text (implementation-specific)
    const warningBadge = usage.getByTestId('usage-warning')
    const limitText = usage.getByText(/approaching plan limit/i)
    const isWarningVisible =
      (await warningBadge.isVisible().catch(() => false)) ||
      (await limitText.isVisible().catch(() => false))

    expect(isWarningVisible).toBeTruthy()
  })

  test('navigation: main nav links from dashboard route to key screens', async ({ page }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const nav = page.getByRole('navigation')

    // Projects
    await nav.getByRole('link', { name: /projects/i }).click()
    await page.waitForURL('**/app/projects')
    await expect(page.getByRole('heading', { name: /project folders/i })).toBeVisible()

    // Back to dashboard
    await nav.getByRole('link', { name: /dashboard/i }).click()
    await page.waitForURL('**/app')
    await waitForDashboardLoaded(page)

    // Templates
    await nav.getByRole('link', { name: /templates/i }).click()
    await page.waitForURL('**/app/templates')
    await expect(page.getByRole('heading', { name: /templates/i })).toBeVisible()

    // Integrations
    await nav.getByRole('link', { name: /integrations/i }).click()
    await page.waitForURL('**/app/integrations')
    await expect(page.getByRole('heading', { name: /integrations/i })).toBeVisible()
  })

  test('user menu: navigate to Usage & Billing only visible for owner', async ({ page }) => {
    await loginAsUser(page, 'owner')
    await waitForDashboardLoaded(page)

    const userMenuTrigger = page.getByTestId('user-menu-trigger')
    await userMenuTrigger.click()
    await expect(page.getByRole('menu')).toBeVisible()

    const billingItem = page.getByRole('menuitem', { name: /usage & billing/i })
    await expect(billingItem).toBeVisible()
    await billingItem.click()

    await page.waitForURL('**/app/settings/usage-billing')
    await expect(page.getByTestId('usage-chart')).toBeVisible()
  })

  test('user menu: readonly user cannot see Usage & Billing', async ({ page }) => {
    await loginAsUser(page, 'readonly')
    await waitForDashboardLoaded(page)

    const userMenuTrigger = page.getByTestId('user-menu-trigger')
    await userMenuTrigger.click()
    await expect(page.getByRole('menu')).toBeVisible()

    await expect(
      page.getByRole('menuitem', { name: /usage & billing/i })
    ).not.toBeVisible({ timeout: 1000 })
  })

  test('error handling: failed /api/usage/summary request shows non-blocking error state', async ({
    page,
  }) => {
    // Intercept usage summary and return 500 to validate UI fallback
    await page.route('**/api/usage/summary', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal error' }),
      })
    })

    await loginAsUser(page, 'owner')
    await waitForDashboardLoaded(page)

    const usage = page.getByTestId('usage-summary')
    await expect(usage).toBeVisible()
    await expect(usage.getByText(/unable to load usage/i)).toBeVisible()
    // Dashboard should still render other widgets
    await expect(page.getByTestId('recent-projects')).toBeVisible()
    await expect(page.getByTestId('latest-extractions')).toBeVisible()
  })

  test('responsive behavior: dashboard layout is usable on mobile breakpoint', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 })
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    // Mobile nav (hamburger / collapsible) should exist
    const mobileNavToggle = page.getByTestId('mobile-nav-toggle')
    await expect(mobileNavToggle).toBeVisible()

    // No horizontal scrollbar at mobile width
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth)
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1)
  })

  test('accessibility basics: dashboard main landmarks and headings', async ({ page }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    // Main landmark
    await expect(page.getByRole('main')).toBeVisible()

    // Navigation landmark
    await expect(page.getByRole('navigation')).toBeVisible()

    // H1 should be the dashboard title
    const h1 = page.getByRole('heading', { level: 1 })
    await expect(h1).toContainText(/dashboard|overview/i)

    // Ensure quick actions are buttons, not plain divs
    const quickActions = page.getByTestId('quick-actions')
    await expect(quickActions.getByRole('button', { name: /upload document/i })).toBeVisible()
  })

  test('theme toggle on dashboard switches between light and dark modes', async ({ page }) => {
    await loginAsUser(page, 'member')
    await waitForDashboardLoaded(page)

    const themeToggle = page.getByTestId('theme-toggle')
    await expect(themeToggle).toBeVisible()

    // Capture initial class on html
    const initialClass = await page.evaluate(
      () => document.documentElement.className || ''
    )

    await themeToggle.click()
    await page.waitForTimeout(300)

    const afterToggleClass = await page.evaluate(
      () => document.documentElement.className || ''
    )
    expect(afterToggleClass).not.toBe(initialClass)

    // Reload to ensure persistence via localStorage
    await page.reload({ waitUntil: 'networkidle' })
    const afterReloadClass = await page.evaluate(
      () => document.documentElement.className || ''
    )
    expect(afterReloadClass).toBe(afterToggleClass)
  })

  test('complete user journey: login -> dashboard -> recent project -> document upload -> back to dashboard', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    // Login
    await page.goto(`${APP_ORIGIN}/login`)
    await browserUse.perform('Fill in the email field with member@example.com')
    await browserUse.perform('Fill in the password field with Password123!')
    await browserUse.perform('Click on the Login button')
    await page.waitForURL('**/app', { waitUntil: 'networkidle' })
    await waitForDashboardLoaded(page)

    // Go to a recent project
    const recentProjects = page.getByTestId('recent-projects')
    const firstProject = recentProjects.getByRole('link').first()
    await firstProject.click()
    await page.waitForURL(/\/app\/projects\//)
    await expect(page.getByTestId('project-tabs')).toBeVisible()

    // Navigate to upload from this project (assume upload button exists)
    const uploadButton = page.getByRole('button', { name: /upload document/i })
    await uploadButton.click()
    await page.waitForURL('**/app/upload')

    // Verify upload form visible
    await expect(page.getByTestId('upload-form')).toBeVisible()

    // Navigate back to dashboard via nav
    await page.getByRole('navigation').getByRole('link', { name: /dashboard/i }).click()
    await page.waitForURL('**/app')
    await waitForDashboardLoaded(page)
  })
})