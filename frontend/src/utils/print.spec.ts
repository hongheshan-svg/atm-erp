import { expect, it } from 'vitest'
import { printFileName } from './print'

it('按单据、对方、单号拼 PDF 默认文件名，跳过空项并去掉文件名非法字符', () => {
  expect(printFileName('采购合同', '东莞市方发五金机电有限公司', 'PO20261123000024', '')).toBe('采购合同-东莞市方发五金机电有限公司-PO20261123000024')
  expect(printFileName('领料单', 'LL000005', null, undefined)).toBe('领料单-LL000005')
  expect(printFileName('采购合同', 'A/B:C*供应商  "一厂"', 'PO1')).toBe('采购合同-A B C 供应商 一厂-PO1')
})
