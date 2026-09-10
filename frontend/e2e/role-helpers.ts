import type { Locator } from './fixtures'

export async function selectRoles(dialog: Locator, roles: string[]) {
  const group = dialog.getByRole('group', { name: '角色', exact: true })
  for (const checkbox of await group.getByRole('checkbox').all()) {
    await checkbox.setChecked(roles.includes(await checkbox.inputValue()))
  }
}
