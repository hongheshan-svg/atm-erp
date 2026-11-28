import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { defaults, payload } from '../forms'
import { draftKey, loadDraft, saveDraft } from '../form-experience'
import { materialDetails, warehouseLines } from '../modules/warehouse-lines'
import { receiptLines } from '../modules/purchases'
import FormFields from './FormFields.vue'
import WarehouseLines from './WarehouseLines.vue'
import type { Row } from '../types'
vi.mock('../api', () => ({ read: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); sessionStorage.clear() })
const material = materialDetails({ item: 1, item_code: '001226000006', item_name: '坦克链安装板', drawing_number: 'A2608-01-00017', specification: '板厚2mm', drawing_revision: 'A', brand: '指定品牌', product_category: '12', part_type: 'custom', unit: 'PCS' })

it('收货表包含截图资料，末列备注；输入按行保留且资料不进入写入请求', async () => {
  const initial = [1, 2].map(line => ({ ...material, line, project_code: 'A2608', assembly_unit: `单元${line}`, required_quantity: '3', remaining: '2', quantity: '1', pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial)
  const data = defaults([field])
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: data } })
  // 1366 宽度下不横向滚动：项目号移到表头，编号与名称、图号型号版本品牌与类型各并成一列，数量输入紧随待收。
  expect(wrapper.findAll('th').map(th => th.text()).slice(1)).toEqual(['产品编号 / 零件名称', '单元', '图号 / 型号 / 版本 / 类型', '单位', '需求数量', '待收数量', '本次合格数量', '不合格隔离数量', '备注'])
  expect(wrapper.get('legend').text()).toContain('项目 A2608')
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 2/2 行，本次合格 2 / 待收 4')
  // 待收 2、本次只填 1：两行都高亮提醒部分到货。
  expect(wrapper.findAll('tbody tr.partial-line')).toHaveLength(2)
  expect(wrapper.text()).toContain('001226000006')
  expect(wrapper.text()).toContain('A2608-01-00017')
  expect(wrapper.text()).toContain('有图·钣金')
  await wrapper.findAll('textarea')[0]!.setValue('第一件备注')
  await wrapper.findAll('textarea')[1]!.setValue('第二件备注')
  expect(payload([field], data)).toEqual({ lines: [
    { line: 1, quantity: '1', pending_quantity: '0', remark: '第一件备注' },
    { line: 2, quantity: '1', pending_quantity: '0', remark: '第二件备注' },
  ] })
  const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!
  await button('全部按待收填入').trigger('click')
  expect(data.lines.map((line: Row) => line.quantity)).toEqual(['2', '2'])
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次合格 4 / 待收 4')
  expect(wrapper.findAll('tbody tr.partial-line')).toHaveLength(0)
  await button('全部清零').trigger('click')
  expect(data.lines.map((line: Row) => line.quantity)).toEqual(['0', '0'])
  wrapper.unmount()
})

it('按 BOM 批量领料：服务端给出需求和未领量，不逐行读取项目需求；默认不勾，勾上按建议数量填入', async () => {
  const initial = [{ ...material, stock: 4, project_code: 'A2608', project_name: '上料线', location: '主仓', required_quantity: '5.000', bom_remaining: '3.000', remaining: '2.000', suggested: '2.000', quantity: '0', selected: false, remark: '' },
    { ...material, stock: 5, project_code: 'A2608', project_name: '上料线', location: '二号仓', required_quantity: '5.000', bom_remaining: '3.000', remaining: '9.000', suggested: '1.000', quantity: '0', selected: false, remark: '' }]
  const field = warehouseLines('issue', initial, { batch: true })
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: initial.map(row => ({ stock: row.stock, selected: false, quantity: '0', remark: '' })), context: { project: 1 } } })
  await flushPromises()
  expect(read).not.toHaveBeenCalled()
  expect(wrapper.findAll('th').map(th => th.text())).toContain('BOM 未领')
  expect(wrapper.get('legend').text()).toContain('项目 A2608 · 上料线')
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 0/2 行，本次出库 0')
  expect(wrapper.findAll('tbody tr.unpicked-line')).toHaveLength(2)
  await wrapper.get('input[aria-label="全选本次领用明细"]').setValue(true)
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 2/2 行，本次出库 3')
  const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!
  await button('取消全部勾选').trigger('click')
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 0/2 行，本次出库 0')
  expect(field.fields!.find(f => f.key === 'quantity')!.numeric!.min).toBe(0)
  wrapper.unmount()
})

it('按 BOM 领料几百行：按非标件 / 标准件筛开，Shift 连选只勾当前筛选下的行，未勾的行不领', async () => {
  const kinds = ['custom', 'standard', 'custom', '', 'custom', 'standard']
  const initial = kinds.map((part_type, i) => ({
    ...materialDetails({ item: i + 1, item_code: `M-${i + 1}`, item_name: `物料${i + 1}`, part_type, product_category: part_type ? '' : '22', unit: 'PCS' }),
    stock: i + 1, project_code: 'A2608', location: '主仓', required_quantity: '2', bom_remaining: '2', remaining: '5', suggested: '2', quantity: '0', selected: false, remark: '',
  }))
  const field = warehouseLines('issue', initial, { batch: true })
  const model = initial.map(row => ({ stock: row.stock, selected: false, quantity: '0', remark: '' }))
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: model, context: { project: 1 } } })
  const filters = () => wrapper.findAll('.warehouse-filter button')
  expect(filters().map(b => b.text())).toEqual(['全部 6', '非标件（机加、钣金） 3', '标准件 / 电气件 2', '未分类 1'])
  await filters()[1]!.trigger('click')
  expect(wrapper.findAll('tbody tr').map(tr => tr.text())).toEqual([expect.stringContaining('物料1'), expect.stringContaining('物料3'), expect.stringContaining('物料5')])
  const boxes = () => wrapper.findAll<HTMLInputElement>('tbody input[type="checkbox"]')
  // 点第 1 行，再按住 Shift 点第 3 行：三行非标件全部勾上，中间被筛掉的标准件不动。
  await boxes()[0]!.trigger('click')
  await boxes()[2]!.trigger('click', { shiftKey: true })
  expect(model.map(row => row.selected)).toEqual([true, false, true, false, true, false])
  expect(model.map(row => row.quantity)).toEqual(['2', '0', '2', '0', '2', '0'])
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 3/6 行，本次出库 6')
  // 全选只作用于当前筛选。
  await filters()[2]!.trigger('click')
  await wrapper.get('thead input[type="checkbox"]').setValue(true)
  expect(model.map(row => row.selected)).toEqual([true, true, true, false, true, true])
  // 取消勾选清零，本行不提交。
  await boxes()[0]!.trigger('click')
  expect(model[1]).toMatchObject({ selected: false, quantity: '0' })
  // 出错的行在别的筛选里时，定位前先切回全部。
  await wrapper.vm.focusPath('lines.3.quantity')
  expect(filters().find(b => b.classes('active'))!.text()).toBe('全部 6')
  wrapper.unmount()
})

it('占用行跨筛选和分页置顶，保留原行号，一次取消只影响冲突行', async () => {
  const initial = Array.from({ length: 229 }, (_, i) => ({
    ...material, stock: i + 1, part_type: i === 228 ? 'standard' : 'custom',
    selected: true, quantity: '3', suggested: '3', remark: '装配',
  }))
  const field = warehouseLines('issue', initial, { batch: true })
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: initial, context: {} } })
  await wrapper.findAll('.warehouse-filter button')[1]!.trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '下一页明细')!.trigger('click')
  await wrapper.setProps({ sharedConflicts: [229, 22].map(stock => ({
    stock: String(stock), requested: '3', overlap: '2', projects: [{ project: 'A2618', quantity: '4' }],
  })) })
  const first = wrapper.findAll('tbody tr').slice(0, 2)
  expect(first.map(tr => tr.get('input').attributes('aria-label'))).toEqual([
    '本次领用：第 22 行 坦克链安装板', '本次领用：第 229 行 坦克链安装板',
  ])
  expect(first.every(tr => tr.classes('conflict-line') && tr.text().includes('型号：板厚2mm'))).toBe(true)
  expect(first[0]!.text()).toContain('其中 2 PCS 会占用其他项目到货。涉及项目：A2618（待领 4 PCS）')
  await wrapper.findAll('button').find(b => b.text().includes('取消勾选全部占用行'))!.trigger('click')
  expect(initial.filter(row => !row.selected).map(row => row.stock)).toEqual([22, 229])
  expect(initial.filter(row => row.selected).every(row => row.quantity === '3' && row.remark === '装配')).toBe(true)
  wrapper.unmount()
})

it('分页错误定位跳到正确页；恢复草稿后仍显示原物料资料', async () => {
  const initial = Array.from({ length: 25 }, (_, i) => ({ ...material, line: i + 1, quantity: '1', pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial)
  const command = { title: '收货', path: '/business/purchases/9/receive/', fields: [field] }
  const data = defaults(command.fields)
  data.lines[24].remark = '末行已填写'
  const key = draftKey(command, 1)
  expect(saveDraft(key, command, data)).toBe(true)
  const restored = loadDraft(key, command)!
  expect(restored.lines[24]).not.toHaveProperty('item_name')
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: restored, issues: { 'lines.24.quantity': '超出数量' } } })
  await wrapper.vm.focusPath('lines.24.quantity')
  expect(wrapper.findAll('tbody tr')).toHaveLength(5)
  expect(wrapper.text()).toContain('坦克链安装板')
  expect(wrapper.text()).toContain('超出数量')
  expect((wrapper.findAll('textarea').at(-1)!.element as HTMLTextAreaElement).value).toBe('末行已填写')
  wrapper.unmount()
})

it('项目切换后清除旧需求，迟到响应不能覆盖新项目，售后不显示BOM限制', async () => {
  let resolveOld!: (value: Row) => void
  vi.mocked(read).mockImplementation(async path => {
    if (path === '/business/projects/1/') return new Promise(resolve => { resolveOld = resolve })
    if (path.endsWith('/demand/')) return { lines: [{ item: 1, quantity: '2.001' }, { item: 1, quantity: '3.002' }, { item: 2, quantity: '99' }] }
    return { code: 'NEW' }
  })
  const field = warehouseLines('issue', [{ ...material, stock: 4, remaining: '10' }])
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: [{ stock: 4, quantity: '1', remark: '' }], context: { project: 1 } } })
  await wrapper.setProps({ context: { project: 2 } })
  await flushPromises()
  expect(wrapper.text()).toContain('NEW')
  expect(wrapper.text()).toContain('5.003')
  resolveOld({ code: 'OLD' }); await flushPromises()
  expect(wrapper.text()).not.toContain('OLD')
  await wrapper.setProps({ context: { project: 2, task: 10 } }); await flushPromises()
  expect(wrapper.text()).toContain('按售后任务领用')
  await wrapper.setProps({ context: {} }); await flushPromises()
  expect(wrapper.text()).not.toContain('NEW')
  expect(wrapper.text()).toContain('请先选择项目')
  wrapper.unmount()
})

it('需求读取失败显示重试提示，不显示旧项目需求', async () => {
  vi.mocked(read).mockRejectedValue(new Error('读取失败'))
  const field = warehouseLines('issue', [{ ...material, stock: 1 }])
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: [{ stock: 1, quantity: '1' }], context: { project: 1 } } })
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('项目需求读取失败')
  vi.mocked(read).mockImplementation(async path => path.endsWith('demand/') ? { lines: [] } : { code: 'A2608' })
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('A2608')
  wrapper.unmount()
})

it('收货逐行勾选到货：取消勾选清零并禁用、不提交，重新勾选恢复待收，全选一键切换', async () => {
  const initial = [1, 2, 3].map(line => ({ ...material, line, item_name: `物料${line}`, required_quantity: '3', remaining: '3.000', quantity: '3.000', selected: true, pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial)
  const data = defaults([field], { lines: initial })
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: data } })
  const row = (n: number) => wrapper.findAll('tbody tr')[n]!
  const pick = (n: number) => row(n).get('input[type="checkbox"]')
  expect(wrapper.get('th').text()).toBe('到货')
  expect(pick(1).attributes('aria-label')).toContain('物料2')
  // 每行输入框按「列名 + 行号与物料」命名：列名仍是可见的简称，读屏能分清是哪一行。
  const nameOf = (input: { attributes: (name: string) => string | undefined }) => input.attributes('aria-labelledby')!.split(' ').map(id => wrapper.get(`[id="${id}"]`).text()).join(' ')
  expect(nameOf(row(1).get('input[id$="-quantity"]'))).toBe('数量 第 2 行 物料2')
  expect(nameOf(row(2).get('textarea'))).toBe('备注 第 3 行 物料3')
  expect(row(1).get('input[id$="-quantity"]').attributes('aria-label')).toBeUndefined()
  await pick(1).setValue(false)
  expect(data.lines[1]).toMatchObject({ selected: false, quantity: '0', pending_quantity: '0' })
  expect(row(1).classes()).toContain('unpicked-line')
  expect((row(1).get('input[id$="-quantity"]').element as HTMLInputElement).disabled).toBe(true)
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 2/3 行，本次合格 6 / 待收 6')
  expect(receiptLines(payload([field], data), { 1: '3.000', 2: '3.000', 3: '3.000' }).lines.map((l: Row) => l.line)).toEqual([1, 3])
  await pick(1).setValue(true)
  expect(data.lines[1]).toMatchObject({ selected: true, quantity: '3.000' })
  const all = wrapper.get('th input[type="checkbox"]')
  await all.setValue(false)
  expect(data.lines.every((l: Row) => l.selected === false && l.quantity === '0')).toBe(true)
  expect(() => receiptLines(payload([field], data), {})).toThrow('请至少勾选一条本次到货的明细')
  await all.setValue(true)
  expect(data.lines.map((l: Row) => l.quantity)).toEqual(['3.000', '3.000', '3.000'])
  wrapper.unmount()
})

it('超过待收在数量下方直接提示并标记输入无效；少于待收时可勾选余量不再到货', async () => {
  const initial = [1, 2].map(line => ({ ...material, line, remaining: '5.000', quantity: '5.000', quarantined: line === 2 ? '1.000' : '0', selected: true, cancel_remainder: false, pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial, { cancel: true })
  const data = defaults([field], { lines: initial })
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: data } })
  const row = (n: number) => wrapper.findAll('tbody tr')[n]!
  const quantity = (n: number) => row(n).get('input[id$="-quantity"]')
  await quantity(0).setValue('7')
  expect(row(0).text()).toContain('超过待收 5：多送部分不能入本单，请联系采购「新建采购」补单后再收。')
  expect((quantity(0).element as HTMLInputElement).validationMessage).toContain('超过待收')
  expect(row(0).classes()).toContain('excess-line')
  expect(row(0).find('.remainder-cancel').exists()).toBe(false)
  expect(() => receiptLines(payload([field], data), { 1: '5.000', 2: '5.000' })).toThrow('第 1 行超过待收 5')
  await quantity(0).setValue('2')
  expect((quantity(0).element as HTMLInputElement).validationMessage).toBe('')
  const cancel = row(0).get('.remainder-cancel input')
  expect(row(0).get('.remainder-cancel').text()).toBe('余量 3 不再到货')
  await cancel.setValue(true)
  expect(row(0).classes()).not.toContain('partial-line')
  expect(receiptLines(payload([field], data), { 1: '5.000', 2: '5.000' }).lines[0]).toEqual({ line: 1, quantity: '2', pending_quantity: '0', cancel_remainder: true })
  // 本次填了隔离数量：与取消余量规则一致须先处理隔离品，已勾选的取消自动撤销。
  await row(0).get('input[id$="-pending_quantity"]').setValue('1')
  await flushPromises()
  expect(data.lines[0].cancel_remainder).toBe(false)
  expect((row(0).get('.remainder-cancel input').element as HTMLInputElement).disabled).toBe(true)
  expect(row(0).text()).toContain('隔离品处理后才能取消余量')
  // 原有到货待检的行同样不能取消。
  await quantity(1).setValue('1')
  expect((row(1).get('.remainder-cancel input').element as HTMLInputElement).disabled).toBe(true)
  expect(row(1).text()).toContain('本行已有到货待检 1')
  // 收足后不再提供取消。
  await quantity(1).setValue('5')
  expect(row(1).find('.remainder-cancel').exists()).toBe(false)
  wrapper.unmount()
})

it('大批收货按明细标识取原始行：行序不同也对得上待收，输入数量时不逐行线性查找原始行', async () => {
  const initial = Array.from({ length: 30 }, (_, i) => ({ ...material, line: i + 1, item_name: `零件${i + 1}`, material_label: `M${i + 1}\n零件${i + 1}`, remaining: `${i + 1}`, quantity: `${i + 1}`, quarantined: '0', pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial, { cancel: true })
  // 恢复草稿只带标识和填写值，顺序也与原始行相反：资料、待收仍按 line 取回。
  const lines = initial.map(row => ({ line: row.line, selected: true, cancel_remainder: false, quantity: row.quantity, pending_quantity: '0', remark: '' })).reverse()
  const find = vi.spyOn(initial, 'find')
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: lines, context: {} } })
  const first = () => wrapper.get('tbody tr')
  expect(wrapper.get('.warehouse-summary').text()).toContain('已勾选 30/30 行，本次合格 465 / 待收 465')
  expect(wrapper.findAll('tbody tr')).toHaveLength(20)
  expect(first().text()).toContain('零件30')
  expect(wrapper.findAll('tbody tr.partial-line')).toHaveLength(0)
  await first().get('input[id$="-quantity"]').setValue('31')
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次合格 466 / 待收 465')
  expect(first().classes()).toContain('excess-line')
  expect(first().text()).toContain('超过待收 30：')
  await first().get('input[id$="-quantity"]').setValue('28')
  expect(first().get('.remainder-cancel').text()).toBe('余量 2 不再到货')
  expect(wrapper.findAll('tbody tr.partial-line')).toHaveLength(1)
  expect(find).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('无采购权限时不提供余量不再到货，只提示由采购取消未收余量', () => {
  const initial = [{ ...material, line: 1, remaining: '5.000', quantity: '2', selected: true, pending_quantity: '0', remark: '' }]
  const field = warehouseLines('receipt', initial)
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: defaults([field], { lines: initial, received_date: '2026-11-10' }) } })
  expect(wrapper.find('.remainder-cancel').exists()).toBe(false)
  expect(wrapper.get('.warehouse-summary').text()).toContain('请采购在「取消未收余量」中处理')
  wrapper.unmount()
})

it('库存勾选批量领料：逐行显示库位，数量默认留空，可一键按可用填入或清空，并读取所选项目需求', async () => {
  const initial = [{ ...material, stock: 1, location: '主仓', remaining: '5.000', quantity: '', remark: '' }, { ...materialDetails({ item: 2, item_code: 'M-2', item_name: '气缸', unit: '个' }), stock: 2, location: '二号仓', remaining: '1.500', quantity: '', remark: '' }]
  vi.mocked(read).mockImplementation(async path => String(path).endsWith('/demand/') ? { lines: [{ item: 1, quantity: '4.000' }] } : { id: 7, code: 'ATM01', name: '上料线' })
  const field = warehouseLines('issue', initial, { location: true })
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: initial.map(row => ({ stock: row.stock, quantity: '', remark: '' })), context: { project: 7 } } })
  await flushPromises()
  expect(wrapper.findAll('th').map(th => th.text()).slice(1)).toEqual(['产品编号 / 零件名称', '库位', '图号 / 型号 / 版本 / 类型', '单位', '需求数量', '本库位可用', '本次出库数量', '备注'])
  expect(wrapper.get('legend').text()).toContain('项目 ATM01 · 上料线')
  // 需求数量与库存列表同一格式：4.000 显示为 4。
  expect(wrapper.findAll('tbody tr')[0]!.get('td.col-required_quantity').text()).toBe('4')
  const button = (text: string) => wrapper.findAll('.warehouse-fill button').find(item => item.text() === text)!
  expect(wrapper.findAll('.warehouse-fill button').map(item => item.text())).toEqual(['全部按可用填入', '全部清空'])
  await button('全部按可用填入').trigger('click')
  expect(wrapper.props('modelValue').map((row: Row) => row.quantity)).toEqual(['5.000', '1.500'])
  await button('全部清空').trigger('click')
  expect(wrapper.props('modelValue').map((row: Row) => row.quantity)).toEqual(['', ''])
  wrapper.unmount()
})
