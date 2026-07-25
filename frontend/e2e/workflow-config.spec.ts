import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('Workflow Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('navigate to workflow config page', async ({ page }) => {
    await page.goto('/erp/workflow/config')
    await expect(page.locator('.workflow-config-sap')).toBeVisible({ timeout: 10000 })
  })

  test('workflow config shows business types', async ({ page }) => {
    await page.goto('/erp/workflow/config')
    const workflowTree = page.locator('.workflow-tree')
    await expect(workflowTree).toBeVisible({ timeout: 10000 })
    await expect(workflowTree).toContainText('销售订单')
  })

  test('can open create workflow dialog', async ({ page }) => {
    await page.goto('/erp/workflow/config')

    await page.getByRole('button', { name: '新建流程', exact: true }).click()
    await expect(page.locator('.el-dialog')).toBeVisible({ timeout: 5000 })
  })

  test('workflow form has business type selector', async ({ page }) => {
    await page.goto('/erp/workflow/config')

    await page.getByRole('button', { name: '新建流程', exact: true }).click()
    const dialog = page.locator('.el-dialog')
    await expect(dialog).toBeVisible({ timeout: 5000 })
    await expect(dialog.locator('.el-select')).toBeVisible()
  })
})
