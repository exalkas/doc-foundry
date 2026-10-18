import { test, expect } from '@playwright/test'
import { BrowserUse } from 'browser-use'

/**
 * Helpers & Fixtures
 */

const TEST_USER = {
  email: 'member@example.com',
  password: 'Password123!',
}

async function loginViaUI(page) {
  const browserUse = new BrowserUse(page)
  await page.goto('/login')
  await browserUse.perform('Fill in the email field with ' + TEST_USER.email)
  await browserUse.perform('Fill in the password field with ' + TEST_USER.password)
  await browserUse.perform('Click the button to log in')
  await page.waitForURL(/\/app(\/)?$/, { waitUntil: 'networkidle' })
  await expect(page).toHaveURL(/\/app(\/)?$/)
  await expect(page.getByText('Project Folders', { exact: false }).or(page.getByText('Projects'))).toBeVisible({ timeout: 10000 }).catch(() => {})
}

async function goToProjectsList(page) {
  const browserUse = new BrowserUse(page)
  await browserUse.perform('Open the Projects or Project Folders section from the dashboard navigation')
  await page.waitForURL(/\/app\/projects/, { waitUntil: 'networkidle' })
  await expect(page).toHaveURL(/\/app\/projects/)
  await expect(
    page.getByRole('heading', { name: /Project Folders|Projects/i }).or(
      page.getByText(/Project Folders|Projects/i)
    )
  ).toBeVisible()
}

/**
 * Page-Object-style helpers for Projects list
 */

class ProjectsPage {
  readonly page

  constructor(page) {
    this.page = page
  }

  async assertOnProjectsPage() {
    await expect(this.page).toHaveURL(/\/app\/projects/)
    await expect(
      this.page.getByRole('heading', { name: /Project Folders|Projects/i }).or(
        this.page.getByText(/Project Folders|Projects/i)
      )
    ).toBeVisible()
  }

  createProjectButton() {
    return this.page
      .getByRole('button', { name: /Create project|New project|Add project/i })
      .or(
        this.page.getByRole('link', { name: /Create project|New project|Add project/i })
      )
  }

  async openCreateProjectModal() {
    const browserUse = new BrowserUse(this.page)
    await browserUse.perform('Click the button to create a new project')
  }

  async fillProjectForm({ name, description }) {
    const browserUse = new BrowserUse(this.page)
    if (name !== undefined) {
      await browserUse.perform('Fill the Project name field with "' + name + '"')
    }
    if (description !== undefined) {
      await browserUse.perform('Fill the Project description field with "' + description + '"')
    }
  }

  async submitProjectForm() {
    const browserUse = new BrowserUse(this.page)
    await browserUse.perform('Submit the project creation form')
  }

  projectRowByName(name) {
    return this.page
      .getByRole('row', { name: new RegExp(name, 'i') })
      .or(this.page.getByText(name).locator('xpath=ancestor::tr'))
  }

  async assertProjectVisible(name) {
    await expect(this.page.getByText(name)).toBeVisible()
  }

  async assertProjectNotVisible(name) {
    await expect(this.page.getByText(name)).not.toBeVisible()
  }

  async openProject(name) {
    const browserUse = new BrowserUse(this.page)
    await browserUse.perform(`In the projects list, click on the project named "${name}" to open it`)
  }

  async openRenameForProject(name) {
    const browserUse = new BrowserUse(this.page)
    await browserUse.perform(`Open the context menu or actions for the project "${name}" and choose Rename`)
  }

  async openDeleteForProject(name) {
    const browserUse = new BrowserUse(this.page)
    await browserUse.perform(`Open the context menu or actions for the project "${name}" and choose Delete`)
  }
}

/**
 * Tests: Projects list screen & project lifecycle
 */

test.describe('Projects - Access control & navigation', () => {
  test('redirects unauthenticated user from /app/projects to login', async ({ page }) => {
    await page.goto('/app/projects')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/login/)
    await expect(
      page.getByRole('heading', { name: /Login|Sign in/i }).or(
        page.getByText(/Login to DocFoundry|Sign in/i)
      )
    ).toBeVisible()
  })

  test('owner/member user can navigate from dashboard to Project Folders', async ({ page }) => {
    await loginViaUI(page)
    await goToProjectsList(page)
    const projectsPage = new ProjectsPage(page)
    await projectsPage.assertOnProjectsPage()
    await expect(projectsPage.createProjectButton()).toBeVisible()
  })
})

test.describe('Projects - Creation', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page)
    await goToProjectsList(page)
  })

  test('happy path: create a new project with name and description', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const projectName = `Invoices - ${Date.now()}`
    const projectDescription = 'All invoice documents'

    await projectsPage.openCreateProjectModal()

    await projectsPage.fillProjectForm({
      name: projectName,
      description: projectDescription,
    })

    await projectsPage.submitProjectForm()

    await browserUse.perform('Wait until the project list updates and shows the new project row')
    await projectsPage.assertProjectVisible(projectName)

    const row = projectsPage.projectRowByName(projectName)
    await expect(row).toContainText(projectName)
    await expect(row).toContainText(/0|documents/i)
  })

  test('validation: cannot create project without name', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)

    await projectsPage.openCreateProjectModal()

    await projectsPage.fillProjectForm({
      name: '',
      description: 'Some description',
    })

    await projectsPage.submitProjectForm()

    const errorLocator = page
      .getByText(/project name is required/i)
      .or(page.getByRole('alert').filter({ hasText: /name/i }))
      .or(page.getByText(/Please enter a project name/i))

    await expect(errorLocator).toBeVisible()
    await expect(page.getByRole('dialog').or(page.locator('[role="dialog"]'))).toBeVisible()
    await browserUse.perform('Close the project creation dialog using the cancel button or close icon')
  })

  test('server error: backend fails when creating project, shows error notification', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const projectName = `Failing Project - ${Date.now()}`

    await page.route('**/api/projects', async (route, request) => {
      if (request.method() === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Unexpected error while creating project' }),
        })
      } else {
        await route.continue()
      }
    })

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: projectName,
      description: 'Should fail',
    })

    await projectsPage.submitProjectForm()

    const errorToast = page
      .getByRole('alert')
      .filter({ hasText: /Unexpected error|Failed to create project|Something went wrong/i })
      .or(page.getByText(/Failed to create project/i))

    await expect(errorToast).toBeVisible()
    await projectsPage.assertProjectNotVisible(projectName)

    await page.unroute('**/api/projects')
    await browserUse.perform('Close any visible error notification if a close button is present')
  })
})

test.describe('Projects - Rename & update', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page)
    await goToProjectsList(page)
  })

  test('rename an existing project from actions menu', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)

    const originalName = `To Rename - ${Date.now()}`
    const newName = `${originalName} (Renamed)`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: originalName,
      description: 'Temp project for rename test',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait until the project list shows the new project we just created')
    await projectsPage.assertProjectVisible(originalName)

    await projectsPage.openRenameForProject(originalName)

    await browserUse.perform(`In the rename dialog or inline editor, replace the project name with "${newName}"`)
    await browserUse.perform('Confirm the rename by clicking the Save or Rename button')

    await browserUse.perform('Wait for the list to refresh with the new project name')
    await projectsPage.assertProjectVisible(newName)
    await projectsPage.assertProjectNotVisible(originalName)
  })

  test('validation: rename with empty name shows error and does not update', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const originalName = `Validation Rename - ${Date.now()}`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: originalName,
      description: 'Rename validation',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait until the project list shows this newly created project')
    await projectsPage.assertProjectVisible(originalName)

    await projectsPage.openRenameForProject(originalName)
    await browserUse.perform('Clear the project name input so it becomes empty')
    await browserUse.perform('Try to save the rename with the empty name')

    const validationError = page
      .getByText(/name is required/i)
      .or(page.getByRole('alert').filter({ hasText: /name/i }))

    await expect(validationError).toBeVisible()

    await browserUse.perform('Cancel the rename operation')
    await projectsPage.assertProjectVisible(originalName)
  })
})

test.describe('Projects - Delete', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page)
    await goToProjectsList(page)
  })

  test('delete an existing project after confirmation', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const projectName = `To Delete - ${Date.now()}`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: projectName,
      description: 'To be deleted',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait until the project appears in the list')
    await projectsPage.assertProjectVisible(projectName)

    await projectsPage.openDeleteForProject(projectName)

    const confirmDialog = page
      .getByRole('dialog')
      .filter({ hasText: /Delete project|Are you sure|This action cannot be undone/i })

    await expect(confirmDialog).toBeVisible()
    await browserUse.perform('In the delete confirmation dialog, confirm deletion by clicking Delete or Confirm')

    await browserUse.perform('Wait for the project row to disappear from the list')
    await projectsPage.assertProjectNotVisible(projectName)
  })

  test('cancel delete from confirmation dialog keeps project', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const projectName = `Cancel Delete - ${Date.now()}`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: projectName,
      description: 'Should not be deleted',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait until the project appears in the list')
    await projectsPage.assertProjectVisible(projectName)

    await projectsPage.openDeleteForProject(projectName)

    const confirmDialog = page
      .getByRole('dialog')
      .filter({ hasText: /Delete project|Are you sure|This action cannot be undone/i })

    await expect(confirmDialog).toBeVisible()
    await browserUse.perform('In the delete confirmation dialog, click Cancel or Close to abort deletion')

    await projectsPage.assertProjectVisible(projectName)
  })

  test('server error on delete shows error and keeps project', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const projectName = `Delete Error - ${Date.now()}`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: projectName,
      description: 'Should fail deletion',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait until this project appears in the list')
    await projectsPage.assertProjectVisible(projectName)

    let deleteProjectId = null
    await page.route('**/api/projects/*', async (route, request) => {
      if (request.method() === 'DELETE') {
        deleteProjectId = request.url().split('/').pop()
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Unable to delete project at this time' }),
        })
      } else {
        await route.continue()
      }
    })

    await projectsPage.openDeleteForProject(projectName)
    await browserUse.perform('Confirm the project deletion in the confirmation dialog')

    const errorToast = page
      .getByRole('alert')
      .filter({ hasText: /Unable to delete project|Failed to delete project|Something went wrong/i })
      .or(page.getByText(/Failed to delete project/i))

    await expect(errorToast).toBeVisible()
    await projectsPage.assertProjectVisible(projectName)

    await page.unroute('**/api/projects/*')
  })
})

test.describe('Projects - Project Detail integration', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page)
    await goToProjectsList(page)
  })

  test('open project detail and verify Documents / Templates tabs', async ({ page }) => {
    const projectsPage = new ProjectsPage(page)
    const browserUse = new BrowserUse(page)
    const projectName = `Detail Project - ${Date.now()}`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: projectName,
      description: 'Detail page test',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait for this new project to be visible in the list')
    await projectsPage.assertProjectVisible(projectName)

    await projectsPage.openProject(projectName)

    await page.waitForURL(/\/app\/projects\/.+/, { waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/\/app\/projects\/.+/)

    await expect(
      page.getByRole('heading', { name: new RegExp(projectName, 'i') }).or(
        page.getByText(projectName)
      )
    ).toBeVisible()

    const docsTab = page.getByRole('tab', { name: /Documents/i }).or(
      page.getByText(/Documents/i)
    )
    const templatesTab = page.getByRole('tab', { name: /Templates/i }).or(
      page.getByText(/Templates/i)
    )

    await expect(docsTab).toBeVisible()
    await expect(templatesTab).toBeVisible()

    await docsTab.click()
    await expect(
      page
        .getByRole('table')
        .or(page.getByText(/No documents yet|Upload your first document/i))
    ).toBeVisible()

    await templatesTab.click()
    await expect(
      page
        .getByRole('table')
        .or(page.getByText(/No templates yet|Create your first template/i))
    ).toBeVisible()
  })

  test('from project detail, navigate to upload document pre-selecting project', async ({ page }) => {
    const browserUse = new BrowserUse(page)
    const projectsPage = new ProjectsPage(page)
    const projectName = `Upload Flow - ${Date.now()}`

    await projectsPage.openCreateProjectModal()
    await projectsPage.fillProjectForm({
      name: projectName,
      description: 'Upload integration',
    })
    await projectsPage.submitProjectForm()
    await browserUse.perform('Wait until this project appears in the list')
    await projectsPage.assertProjectVisible(projectName)

    await projectsPage.openProject(projectName)
    await page.waitForURL(/\/app\/projects\/.+/)

    await browserUse.perform('Within the project detail page, click the button to upload a document')
    await page.waitForURL(/\/app\/upload/)
    await expect(page).toHaveURL(/\/app\/upload/)

    const projectSelector = page
      .getByLabel(/Project/i)
      .or(page.getByRole('combobox', { name: /Project/i }))
      .or(page.getByRole('button', { name: new RegExp(projectName, 'i') }))

    await expect(projectSelector).toBeVisible()
  })
})

test.describe('Projects - Pagination and empty state', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page)
    await goToProjectsList(page)
  })

  test('shows empty state when no projects exist', async ({ page }) => {
    const browserUse = new BrowserUse(page)

    await page.route('**/api/projects?**', async (route, request) => {
      if (request.method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ projects: [] }),
        })
      } else {
        await route.continue()
      }
    })

    await page.reload({ waitUntil: 'networkidle' })

    const emptyState = page
      .getByText(/No projects yet|Create your first project|Get started by creating a project/i)
      .or(page.getByRole('status').filter({ hasText: /no projects/i }))

    await expect(emptyState).toBeVisible()
    const projectsPage = new ProjectsPage(page)
    await expect(projectsPage.createProjectButton()).toBeVisible()

    await page.unroute('**/api/projects?**')
    await browserUse.perform('Optionally create a project to reset state if subsequent tests depend on data')
  })

  test('supports navigating between pages of projects if pagination controls exist', async ({ page }) => {
    const browserUse = new BrowserUse(page)

    const nextButton = page
      .getByRole('button', { name: /Next|›|→/i })
      .or(page.getByRole('link', { name: /Next/i }))
    const prevButton = page
      .getByRole('button', { name: /Previous|Prev|‹|←/i })
      .or(page.getByRole('link', { name: /Previous|Prev/i }))

    if (!(await nextButton.isVisible().catch(() => false))) {
      test.skip(true, 'Pagination controls are not visible; skipping pagination test')
    }

    const firstPageRowText = await page
      .getByRole('row')
      .nth(1)
      .innerText()
      .catch(() => '')

    await nextButton.click()
    await browserUse.perform('Wait for the project list to load the next page')
    const secondPageRowText = await page
      .getByRole('row')
      .nth(1)
      .innerText()
      .catch(() => '')

    expect(secondPageRowText).not.toEqual(firstPageRowText)

    await prevButton.click()
    await browserUse.perform('Wait for the project list to load the previous page')
    const backToFirstPageRowText = await page
      .getByRole('row')
      .nth(1)
      .innerText()
      .catch(() => '')

    expect(backToFirstPageRowText).toEqual(firstPageRowText)
  })
})

test.describe('Projects - Role-based behavior for readonly users', () => {
  test('readonly user can view but not create or delete projects', async ({ page }) => {
    const browserUse = new BrowserUse(page)

    await page.route('**/api/auth/login', async (route, request) => {
      const body = JSON.parse(request.postData() || '{}')
      if (body.email === 'readonly@example.com') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            token: 'fake-token',
            user: {
              id: 'readonly-user-id',
              email: body.email,
              global_role: 'user',
            },
            workspaces: [
              {
                id: 'workspace-id',
                name: 'Test Workspace',
              },
            ],
            current_workspace: {
              id: 'workspace-id',
              name: 'Test Workspace',
              role: 'readonly',
            },
          }),
        })
      }
      await route.continue()
    })

    await page.goto('/login')
    await browserUse.perform('Fill in the email field with readonly@example.com')
    await browserUse.perform('Fill in the password field with any value, for example "Password123!"')
    await browserUse.perform('Click the button to log in')
    await page.waitForURL(/\/app(\/)?$/)

    await goToProjectsList(page)
    const projectsPage = new ProjectsPage(page)
    await projectsPage.assertOnProjectsPage()

    const createButtonVisible = await projectsPage
      .createProjectButton()
      .isVisible()
      .catch(() => false)
    expect(createButtonVisible).toBeFalsy()

    const anyDeleteButton = page
      .getByRole('button', { name: /Delete/i })
      .or(page.getByRole('menuitem', { name: /Delete/i }))
    const deleteVisible = await anyDeleteButton.isVisible().catch(() => false)
    expect(deleteVisible).toBeFalsy()
  })
})

test.describe('Projects - Responsive behavior checks', () => {
  for (const width of [375, 768, 1280]) {
    test(`projects list is usable at width ${width}px without horizontal scroll`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await loginViaUI(page)
      await goToProjectsList(page)

      const horizontalOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth
      })

      expect(horizontalOverflow).toBeFalsy()
      await expect(
        page.getByRole('heading', { name: /Projects|Project Folders/i }).or(
          page.getByText(/Projects|Project Folders/i)
        )
      ).toBeVisible()
    })
  }
})