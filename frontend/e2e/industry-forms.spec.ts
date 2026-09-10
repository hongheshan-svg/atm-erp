import { test, expect, login } from './fixtures'

test('设备需求提示、整数校验和多行输入适应桌面与移动端', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/projects')
  await page.getByRole('button', { name: '新建项目', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新建项目', exact: true })
  const requirements = dialog.getByLabel('需求说明', { exact: true })
  await expect(requirements).toHaveAttribute('placeholder', /节拍/)
  await expect(requirements).toHaveValue('')
  await expect(dialog.getByLabel('计划交期', { exact: true })).toHaveValue('')
  await requirements.fill('产品：电机转子\n节拍：待客户确认\n验收：连续运行测试')
  await expect(requirements).toHaveValue(/\n/)
  await dialog.getByLabel('项目名称', { exact: true }).fill('自动装配检测线 · 表单校验')
  for (const label of ['客户', '负责人']) {
    const select = dialog.getByLabel(label, { exact: true })
    const first = await select.locator('option').nth(1).getAttribute('value')
    await select.selectOption(first!)
  }
  await page.screenshot({ path: info.outputPath('industry-project-form.png'), fullPage: true, animations: 'disabled' })
  await dialog.getByLabel('设备数量', { exact: true }).fill('1.5')
  let writes = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/api/business/projects/')) writes++ })
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('整数')
  expect(writes).toBe(0)
  await dialog.getByLabel('设备数量', { exact: true }).fill('1')
  await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeInViewport()
  await page.screenshot({ path: info.outputPath('industry-project-validation.png'), fullPage: true, animations: 'disabled' })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  expect(writes).toBe(0)
})
