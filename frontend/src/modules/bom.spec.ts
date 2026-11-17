import { afterEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { user } from '../session'
import { actionCommand, actionNames, bomCommand, revisionResult, unitNames } from './bom'

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
  expect(command.notice!.text).toContain('旧版待处理')
  expect(command.initial).toMatchObject({ quantity: '2', required_date: '2026-12-01' })
  expect(command.prepare!({ item: 9, quantity: '3', change_note: 'B版', required_date: '2026-12-01' })).toEqual({ item: 9, quantity: '3', change_note: 'B版', required_date: '2026-12-01', application_date: null, applicant: '' })
  expect(read).not.toHaveBeenCalled()
})

it('带图号的非标件可一步升版：默认只改本项目，可勾选同物料的其他项目，不能维护的项目写在提示里', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  const row = { id: 5, project: 81, item: 7, item_code: 'JG-001', item_name: '夹爪安装板', specification: '6061', drawing_number: 'DWG-001', drawing_revision: 'A', quantity: '10', assembly_unit: '01 上料', can_edit_bom: true }
  expect(actionNames('bom', row)).toEqual(['修改此行', '升版', '替换物料', '移除'])
  vi.mocked(read).mockResolvedValue([
    { id: 90, code: 'ATM2690', name: '下料线', quantity: '4.000', units: ['02 搬运'], writable: true },
    { id: 91, code: 'ATM2691', name: '包装线', quantity: '2.000', units: ['未分单元'], writable: false },
  ])
  const command = await actionCommand('bom', row, '升版')
  expect(read).toHaveBeenCalledWith('/business/bom/5/upgrade-scope/')
  expect(command.path).toBe('/business/bom/5/upgrade/')
  expect(command.notice!.text).toContain('按新图改单')
  expect(command.notice!.text).toContain('ATM2691')
  const scope = command.fields.find(field => field.key === 'projects')!
  expect(scope.options).toEqual([{ value: 90, label: 'ATM2690 下料线（02 搬运，共 4）' }])
  expect(command.initial).toMatchObject({ projects: [], quantity: '10' })
  expect(command.prepare!({ drawing_revision: 'B', name: '', specification: '6061 加厚', quantity: '10', change_note: 'ECN-1', projects: [90] }))
    .toEqual({ drawing_revision: 'B', specification: '6061 加厚', quantity: '10', change_note: 'ECN-1', projects: [90] })
  expect(revisionResult({ item_code: 'JG-001C', created_item: true, converted: [{ code: 'PO-1', pending: true }, { code: 'PO-2', pending: false }], projects: [{ code: 'ATM2690', changes: [{ converted: [{ code: 'PO-3', pending: true }] }] }] }))
    .toBe('新版物料 JG-001C（新建）。已同时换版：ATM2690。未批准的采购 PO-2 已直接改成新版。已批准的采购 PO-1、PO-3 已转新版，待采购向供应商确认。')
  // 没有图号的标准件换型号仍用替换物料。
  expect(actionNames('bom', { ...row, drawing_number: '' })).toEqual(['修改此行', '替换物料', '移除'])
})

it('移除确认写明物料编码、名称、单元和数量', async () => {
  const command = await actionCommand('bom', { id: 9, project: 7, item_code: 'PK110001', item_name: '电芯连接法兰', assembly_unit: '01 电芯上料工位', quantity: '2.000', unit: '件' }, '移除')
  expect(command.title).toBe('移除 PK110001 电芯连接法兰（01 电芯上料工位）')
  expect(command.submitLabel).toBe('确认移除')
  expect(command.path).toBe('/business/bom/9/remove/')
  expect(command.notice?.text).toContain('需求 2 件')
})
