import { expect, type Locator } from './fixtures'

// 勾选给定角色、取消其余角色。先等要勾选的每个角色都已出现，免得角色列表未渲染完就逐项设置；
// 不核对角色总数，新增角色不必改各用例。
export async function selectRoles(dialog: Locator, roles: string[]) {
  const group = dialog.getByRole('group', { name: '角色', exact: true })
  for (const role of roles) await expect(group.locator(`input[type="checkbox"][value="${role}"]`), `角色选项：${role}`).toHaveCount(1)
  for (const checkbox of await group.getByRole('checkbox').all()) {
    await checkbox.setChecked(roles.includes(await checkbox.inputValue()))
  }
}
