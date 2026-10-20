import { expect, type Locator } from '@playwright/test'

export function remoteControl(field: Locator) {
  return field.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " remote-select ")][1]')
}
export async function searchRemote(field: Locator, search = '') {
  await expect(field).toHaveAttribute('role', 'combobox')
  await field.click()
  await field.fill(search)
  const control = remoteControl(field)
  await expect(control.getByRole('listbox')).toHaveAttribute('aria-busy', 'false')
  await expect(control.getByRole('alert')).toHaveCount(0)
  return control
}
export async function selectRemoteOption(field: Locator, choice: { text?: string; id?: string | number } = {}) {
  const control = await searchRemote(field, choice.text ?? '')
  const candidates = () => choice.id != null
    ? control.getByRole('option').and(control.locator(`[data-value="${choice.id}"]`))
    : choice.text ? control.getByRole('option').filter({ hasText: choice.text }) : control.getByRole('option').first()
  while (await candidates().count() === 0) {
    const more = control.getByRole('button', { name: '继续加载更多', exact: true })
    await expect(more, `找不到远程选项：${choice.text ?? choice.id ?? '第一项'}`).toBeVisible()
    await more.click()
    await expect(control.getByRole('listbox')).toHaveAttribute('aria-busy', 'false')
    await expect(control.getByRole('alert')).toHaveCount(0)
  }
  // 同名资料必须补充编号或稳定ID，不能默默取最后一项。
  await expect(candidates(), '重名选项需用编号或ID区分').toHaveCount(1)
  await candidates().click()
  await expect(field).toHaveAttribute('aria-expanded', 'false')
}
export async function clearRemote(field: Locator) {
  const control = remoteControl(field)
  const clear = control.getByRole('button', { name: /^清空/ })
  if (await clear.count()) await clear.click()
  await field.press('Escape')
  await expect(field).toHaveValue('')
}
