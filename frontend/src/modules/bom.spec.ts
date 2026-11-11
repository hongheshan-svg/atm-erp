import { afterEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { user } from '../session'
import { actionCommand, actionNames, bomCommand, unitNames } from './bom'

vi.mock('../api', () => ({ read: vi.fn() }))
afterEach(() => { user.value = null; vi.resetAllMocks() })
const lines = [{ assembly_unit: '10 下料' }, { assembly_unit: '01 电芯上料工位' }, { assembly_unit: '' }, { assembly_unit: '2 检测' }, { assembly_unit: '01 电芯上料工位' }]

it('单元候选取本项目现有单元，去重并按编号自然排序', () => {
  expect(unitNames(lines)).toEqual(['01 电芯上料工位', '2 检测', '10 下料'])
})

it('维护 BOM 与修改此行的单元输入都给现有单元候选，说明写明多单元物料必须填单元', async () => {
  vi.mocked(read).mockResolvedValue({ revision: 'r1', lines })
  const maintain = await bomCommand(81)
  const unit = maintain.fields[0]!.fields!.find(field => field.key === 'assembly_unit')!
  expect(unit.suggestions).toEqual(['01 电芯上料工位', '2 检测', '10 下料'])
  expect(maintain.notice!.text).toContain('物料已在多个单元有用料时不能留空')
  expect(maintain.notice!.text).toContain('不会移除未列出的行')
  const single = await actionCommand('bom', { id: 5, project: 81, item: 7, item_code: 'A', item_name: '支架', quantity: '2', assembly_unit: '2 检测' }, '修改此行')
  expect(single.fields.find(field => field.key === 'assembly_unit')!.suggestions).toContain('10 下料')
})

it('替换物料一次提交新物料并移除原行，保留原单元与日期', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  const row = { id: 5, project: 81, item: 7, item_code: 'A', item_name: '支架', quantity: '2', assembly_unit: '03 检测', required_date: '2026-12-01', can_edit_bom: true }
  expect(actionNames('bom', row)).toEqual(['修改此行', '替换物料', '移除'])
  const command = await actionCommand('bom', row, '替换物料')
  expect(command.path).toBe('/business/bom/5/replace/')
  expect(command.submitLabel).toBe('确认替换')
  expect(command.notice!.text).toContain('「03 检测」')
  expect(command.initial).toMatchObject({ quantity: '2', required_date: '2026-12-01' })
  expect(command.prepare!({ item: 9, quantity: '3', change_note: 'B版', required_date: '2026-12-01' })).toEqual({ item: 9, quantity: '3', change_note: 'B版', required_date: '2026-12-01', application_date: null, applicant: '' })
  expect(read).not.toHaveBeenCalled()
})
