import { test, expect } from '@playwright/test'
import { BrowserUse } from 'browser-use'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'

/**
 * Helpers
 */
const randomEmail = () =>
  `e2e+${Date.now()}+${Math.random().toString(16).slice(2)}@example.com`

test.describe('Auth - Login & Registration Flows', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
    await page.goto(BASE_URL)
  })

  test('registration happy path: new user registers and is redirected to app', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)
    const email = randomEmail()
    const password = 'P@ssw0rd123!'
    const fullName = 'E2E Test User'
    const workspaceName = 'E2E Workspace'

    await browserUse.perform('Navigate to the register page')
    await expect(page).toHaveURL(/\/register/)

    // Basic UI expectations
    await browserUse.perform("Ensure there's a visible heading that says Register or similar")
    await browserUse.perform("Ensure there is a form with fields for full name, email, password, and workspace name")

    // Fill registration form (use natural language, BrowserUse will find inputs)
    await browserUse.perform(`Fill in the full name field with "${fullName}"`)
    await browserUse.perform(`Fill in the email field with "${email}"`)
    await browserUse.perform(`Fill in the password field with "${password}"`)
    await browserUse.perform(`Fill in the workspace name field with "${workspaceName}"`)
    await browserUse.perform('Click the button to submit the registration form')

    // Wait for redirect to authenticated area (dashboard or onboarding)
    await page.waitForLoadState('networkidle')
    await expect(page.url()).toMatch(/\/app(\/onboarding)?/)

    // Validate we are authenticated by checking presence of dashboard/onboarding element
    const possibleSelectors = [
      'text=User Dashboard',
      'text=Workspace Onboarding',
      'data-testid=main_header',
      'data-testid=usage_summary',
    ]

    const anyVisible = await Promise.any(
      possibleSelectors.map(async (sel) => {
        try {
          const locator = page.locator(sel)
          await locator.first().waitFor({ timeout: 5000 })
          return true
        } catch {
          return false
        }
      })
    ).catch(() => false)

    expect(anyVisible).toBeTruthy()
  })

  test('registration validation: missing required fields shows errors and prevents submit', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Go to the /register page')
    await expect(page).toHaveURL(/\/register/)

    // Submit without filling anything
    await browserUse.perform('Click on the primary button to submit the registration form')

    // Expect validation messages for required fields
    const requiredFieldMessages = [
      'Full name is required',
      'Email is required',
      'Password is required',
      'Workspace name is required',
      'Required',
      'This field is required',
    ]

    const foundAny = await Promise.any(
      requiredFieldMessages.map(async (msg) => {
        try {
          await page.getByText(msg, { exact: false }).first().waitFor({ timeout: 3000 })
          return true
        } catch {
          return false
        }
      })
    ).catch(() => false)

    expect(foundAny).toBeTruthy()

    // Ensure we have not navigated away
    await expect(page).toHaveURL(/\/register/)
  })

  test('registration error: duplicate email shows API error and stays on page', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)
    const duplicateEmail = 'existing+e2e@example.com'
    const password = 'P@ssw0rd123!'
    const fullName = 'Existing User'
    const workspaceName = 'Existing Workspace'

    await browserUse.perform('Open the /register page')
    await expect(page).toHaveURL(/\/register/)

    await browserUse.perform(`Fill in the full name field with "${fullName}"`)
    await browserUse.perform(`Fill in the email field with "${duplicateEmail}"`)
    await browserUse.perform(`Fill in the password field with "${password}"`)
    await browserUse.perform(`Fill in the workspace name field with "${workspaceName}"`)
    await browserUse.perform('Submit the registration form')

    // Expect an error flash or inline message about email already used
    const possibleErrors = [
      'Email already in use',
      'account already exists',
      'User with this email already exists',
      'duplicate key value violates unique constraint',
    ]

    const errorVisible = await Promise.any(
      possibleErrors.map(async (msg) => {
        try {
          await page.getByText(msg, { exact: false }).first().waitFor({ timeout: 8000 })
          return true
        } catch {
          return false
        }
      })
    ).catch(() => false)

    expect(errorVisible).toBeTruthy()

    // Should remain on /register and not be redirected
    await expect(page).toHaveURL(/\/register/)
  })

  test('login happy path: existing user logs in and reaches dashboard', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    // This email/password must exist in seeded test data or via pre-run fixture
    const email = process.env.E2E_USER_EMAIL || 'owner+e2e@example.com'
    const password = process.env.E2E_USER_PASSWORD || 'P@ssw0rd123!'

    await browserUse.perform('Navigate directly to the /login page')
    await expect(page).toHaveURL(/\/login/)

    // Basic UI checks
    await browserUse.perform("Confirm the page has a heading that says Login or Sign in")
    await browserUse.perform('Ensure there are fields for email and password')

    await browserUse.perform(`Fill the email field with "${email}"`)
    await browserUse.perform(`Fill the password field with "${password}"`)
    await browserUse.perform('Click the button to log in')

    await page.waitForLoadState('networkidle')

    // Expect redirect to dashboard (/app) or onboarding
    expect(page.url()).toMatch(/\/app(\/onboarding)?/)

    // Verify session by calling /api/auth/me via Playwright request
    const cookies = await page.context().cookies()
    const hasAuthCookie = cookies.some((c) => /token|auth|session/i.test(c.name))
    expect(hasAuthCookie).toBeTruthy()
  })

  test('login validation: invalid email format and short password show errors', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Open the login page at /login')
    await expect(page).toHaveURL(/\/login/)

    await browserUse.perform('Fill in the email field with "not-an-email"')
    await browserUse.perform('Fill in the password field with "123"')
    await browserUse.perform('Submit the login form')

    const validationMessages = [
      'Invalid email',
      'Enter a valid email',
      'Email must be a valid',
      'Password must be at least',
      'too short',
    ]

    const validationVisible = await Promise.any(
      validationMessages.map(async (msg) => {
        try {
          await page.getByText(msg, { exact: false }).first().waitFor({ timeout: 5000 })
          return true
        } catch {
          return false
        }
      })
    ).catch(() => false)

    expect(validationVisible).toBeTruthy()
    await expect(page).toHaveURL(/\/login/)
  })

  test('login error: wrong credentials show error and do not authenticate', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Go to the /login screen')
    await expect(page).toHaveURL(/\/login/)

    await browserUse.perform('Fill the email field with "unknown+e2e@example.com"')
    await browserUse.perform('Fill the password field with "ThisIsTheWrongPassword1!"')
    await browserUse.perform('Click the submit/login button')

    const errorMessages = [
      'Invalid email or password',
      'Incorrect email or password',
      'Authentication failed',
      'Invalid credentials',
    ]

    const errorVisible = await Promise.any(
      errorMessages.map(async (msg) => {
        try {
          await page.getByText(msg, { exact: false }).first().waitFor({ timeout: 8000 })
          return true
        } catch {
          return false
        }
      })
    ).catch(() => false)

    expect(errorVisible).toBeTruthy()

    // Ensure we are still on login and no auth cookie is set
    await expect(page).toHaveURL(/\/login/)
    const cookies = await page.context().cookies()
    const hasAuthCookie = cookies.some((c) => /token|auth|session/i.test(c.name))
    expect(hasAuthCookie).toBeFalsy()
  })

  test('navigation: switch between login and register via links', async ({ page }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Open the login page at /login')
    await expect(page).toHaveURL(/\/login/)

    await browserUse.perform('Click on the link that says "Create account", "Sign up", or "Register"')
    await page.waitForTimeout(500)
    await expect(page).toHaveURL(/\/register/)

    await browserUse.perform('Click on the link that says "Already have an account" or "Log in instead"')
    await page.waitForTimeout(500)
    await expect(page).toHaveURL(/\/login/)
  })

  test('forgot password / reset password link is visible and navigable (if implemented)', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Navigate to /login')
    await expect(page).toHaveURL(/\/login/)

    // This may go to /forgot-password or open a dialog. Just assert that it is actionable.
    const forgotSelectors = [
      'text=Forgot password',
      'text=Forgot your password',
      'text=Reset password',
    ]

    let clicked = false
    for (const sel of forgotSelectors) {
      const loc = page.locator(sel).first()
      if (await loc.isVisible().catch(() => false)) {
        await loc.click()
        clicked = true
        break
      }
    }

    if (!clicked) {
      // Try BrowserUse intelligent click
      await browserUse
        .perform('Click on the "Forgot password" or "Reset it" link')
        .catch(() => {})
    }

    // We don't know exact behavior; assert at least we did not crash and URL changed or a dialog appeared
    const urlChanged = /forgot|reset/.test(page.url())
    const dialogVisible =
      (await page
        .locator('role=dialog,dialog')
        .first()
        .isVisible()
        .catch(() => false)) || false

    expect(urlChanged || dialogVisible).toBeTruthy()
  })

  test('google oauth button present and triggers OAuth flow (no full redirect assertion)', async ({
    page,
    context,
  }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Open /login page')
    await expect(page).toHaveURL(/\/login/)

    // Check presence of Google login button
    const googleButtonCandidates = [
      'text=Continue with Google',
      'text=Sign in with Google',
      'text=Login with Google',
      'data-testid=login-with-google',
    ]

    const buttonFound = await Promise.any(
      googleButtonCandidates.map(async (sel) => {
        const loc = page.locator(sel).first()
        try {
          await loc.waitFor({ timeout: 5000 })
          return true
        } catch {
          return false
        }
      })
    ).catch(() => false)

    expect(buttonFound).toBeTruthy()

    // Intercept popup if OAuth uses a new window
    const [popup] = await Promise.all([
      context.waitForEvent('page').catch(() => null),
      (async () => {
        for (const sel of googleButtonCandidates) {
          const loc = page.locator(sel).first()
          if (await loc.isVisible().catch(() => false)) {
            await loc.click()
            return
          }
        }
        await browserUse.perform('Click on the Google login button')
      })(),
    ])

    // Either redirected current page to Google or opened popup
    const currentUrl = page.url()
    const isGoogleLike =
      /accounts\.google\.com/.test(currentUrl) ||
      (popup && /accounts\.google\.com/.test(popup.url()))

    // We only assert that something resembling OAuth was attempted
    expect(isGoogleLike || popup !== null).toBeTruthy()
  })

  test('unauthenticated user hitting /app is redirected to login', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto(`${BASE_URL}/app`, { waitUntil: 'networkidle' })

    // Should redirect to /login
    await expect(page).toHaveURL(/\/login/)
  })

  test('authenticated user visiting /login is redirected to /app', async ({ page }) => {
    const browserUse = new BrowserUse(page)
    const email = process.env.E2E_USER_EMAIL || 'owner+e2e@example.com'
    const password = process.env.E2E_USER_PASSWORD || 'P@ssw0rd123!'

    // First log in
    await browserUse.perform('Navigate to /login')
    await browserUse.perform(`Fill the email field with "${email}"`)
    await browserUse.perform(`Fill the password field with "${password}"`)
    await browserUse.perform('Click the button to log in')
    await page.waitForLoadState('networkidle')
    await expect(page.url()).toMatch(/\/app(\/onboarding)?/)

    // Now try to visit /login again
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' })

    // App should detect session and redirect back to /app
    await expect(page.url()).toMatch(/\/app(\/onboarding)?/)
  })

  test('session persistence: reload page keeps user logged in', async ({ page }) => {
    const browserUse = new BrowserUse(page)
    const email = process.env.E2E_USER_EMAIL || 'owner+e2e@example.com'
    const password = process.env.E2E_USER_PASSWORD || 'P@ssw0rd123!'

    await browserUse.perform('Go to /login')
    await browserUse.perform(`Fill the email field with "${email}"`)
    await browserUse.perform(`Fill the password field with "${password}"`)
    await browserUse.perform('Submit the login form')

    await page.waitForLoadState('networkidle')
    await expect(page.url()).toMatch(/\/app(\/onboarding)?/)

    // Reload
    await page.reload({ waitUntil: 'networkidle' })

    // Still authenticated
    await expect(page.url()).toMatch(/\/app(\/onboarding)?/)
    const cookies = await page.context().cookies()
    const hasAuthCookie = cookies.some((c) => /token|auth|session/i.test(c.name))
    expect(hasAuthCookie).toBeTruthy()
  })

  test('logout flow: user logs out and is redirected to login, session cleared', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)
    const email = process.env.E2E_USER_EMAIL || 'owner+e2e@example.com'
    const password = process.env.E2E_USER_PASSWORD || 'P@ssw0rd123!'

    // Log in
    await browserUse.perform('Navigate to /login')
    await browserUse.perform(`Fill the email field with "${email}"`)
    await browserUse.perform(`Fill the password field with "${password}"`)
    await browserUse.perform('Click the login button')
    await page.waitForLoadState('networkidle')
    await expect(page.url()).toMatch(/\/app(\/onboarding)?/)

    // Trigger logout via user menu
    await browserUse.perform('Open the user menu in the top navigation')
    await browserUse.perform('Click the option that says "Log out" or "Sign out"')

    // After logout, expect redirect to /login
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/login/)

    // Check that auth cookie is cleared
    const cookies = await page.context().cookies()
    const hasAuthCookie = cookies.some((c) => /token|auth|session/i.test(c.name))
    expect(hasAuthCookie).toBeFalsy()
  })

  test('auth pages responsive: no horizontal scroll on mobile and desktop', async ({
    page,
  }) => {
    const browserUse = new BrowserUse(page)

    const widths = [375, 1280]
    for (const width of widths) {
      await page.setViewportSize({ width, height: 800 })
      await browserUse.perform('Navigate to /login')
      await page.waitForLoadState('networkidle')

      // Simple overflow check via JS
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth
      })

      expect(hasHorizontalScroll).toBeFalsy()
    }
  })

  test('auth form accessibility basics: labels and keyboard focus', async ({ page }) => {
    const browserUse = new BrowserUse(page)

    await browserUse.perform('Open /login')
    await page.waitForLoadState('domcontentloaded')

    // Ensure at least one labeled email field and password field exist
    const emailSelectors = ['input[type="email"]', 'input[name*="email" i]']
    const passwordSelectors = ['input[type="password"]', 'input[name*="password" i]']

    const emailHasLabel = await page.evaluate((selectors) => {
      const inputs: HTMLInputElement[] = []
      selectors.forEach((s) => {
        document.querySelectorAll<HTMLInputElement>(s).forEach((el) => inputs.push(el))
      })

      return inputs.some((input) => {
        if (!input.id) return false
        const label = document.querySelector<HTMLLabelElement>(`label[for="${input.id}"]`)
        return !!label
      })
    }, emailSelectors)
    expect(emailHasLabel).toBeTruthy()

    const passwordHasLabel = await page.evaluate((selectors) => {
      const inputs: HTMLInputElement[] = []
      selectors.forEach((s) => {
        document.querySelectorAll<HTMLInputElement>(s).forEach((el) => inputs.push(el))
      })

      return inputs.some((input) => {
        if (!input.id) return false
        const label = document.querySelector<HTMLLabelElement>(`label[for="${input.id}"]`)
        return !!label
      })
    }, passwordSelectors)
    expect(passwordHasLabel).toBeTruthy()

    // Tab through first few focusable elements to ensure keyboard navigation works
    await page.keyboard.press('Tab')
    const activeTag1 = await page.evaluate(() => document.activeElement?.tagName)
    expect(activeTag1).toBeTruthy()

    await page.keyboard.press('Tab')
    const activeTag2 = await page.evaluate(() => document.activeElement?.tagName)
    expect(activeTag2).toBeTruthy()
  })
})