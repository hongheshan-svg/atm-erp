import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import BOMList from '../BOMList.vue'

const getBOMList = vi.fn()
const getBOMPendingQuoteCount = vi.fn()
const importBOMExcel = vi.fn()
const getProjectList = vi.fn()
const getUsers = vi.fn()
const getItemList = vi.fn()
const getSupplierList = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/projects/bom', () => ({
  getBOMList: (...args: any[]) => getBOMList(...args),
  getBOMPendingQuoteCount: (...args: any[]) => getBOMPendingQuoteCount(...args),
  importBOMExcel: (...args: any[]) => importBOMExcel(...args),
  createBOM: vi.fn(),
  updateBOM: vi.fn(),
  deleteBOM: vi.fn(),
  bulkDeleteBOM: vi.fn(),
  exportBOMExcel: vi.fn(),
  exportBOMForQuote: vi.fn(),
  exportBOMTemplate: vi.fn(),
  exportQuoteBOM: vi.fn(),
  importQuoteBOM: vi.fn(),
  copyBOMFromProject: vi.fn(),
  getBOMMaterialCheck: vi.fn(),
}))

vi.mock('@/api/projects/project', () => ({
  getProjectList: (...args: any[]) => getProjectList(...args),
}))

vi.mock('@/api/auth', () => ({
  getUsers: (...args: any[]) => getUsers(...args),
}))

vi.mock('@/api/masterdata', () => ({
  getItemList: (...args: any[]) => getItemList(...args),
  getSupplierList: (...args: any[]) => getSupplierList(...args),
}))

describe('BOMList import', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getBOMList.mockResolvedValue({ results: [], count: 0 })
    getBOMPendingQuoteCount.mockResolvedValue({ count: 0 })
    getProjectList.mockResolvedValue({ results: [{ id: 1, code: 'P1', name: '测试项目' }] })
    getUsers.mockResolvedValue({ results: [] })
    getItemList.mockResolvedValue({ results: [] })
    getSupplierList.mockResolvedValue({ results: [] })
  })

  it('把导入校验失败展示在对话框且不写 console error', async () => {
    const validationError = {
      response: {
        status: 400,
        data: {
          error: '校验失败，未导入任何数据',
          errors: [{ row: 2, error: '计划数量必须大于0' }],
        },
      },
    }
    importBOMExcel.mockRejectedValue(validationError)
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const wrapper = mount(BOMList)
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedProject = 1
    vm.importFile = new File(['invalid'], 'bom.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    await vm.handleConfirmImport()
    await flushPromises()

    expect(importBOMExcel).toHaveBeenCalledWith(expect.any(FormData), { skipErrorMessage: true })
    expect(vm.importResult).toEqual(validationError.response.data)
    expect(consoleError).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('导入校验未通过，请查看详情')
    consoleError.mockRestore()
  })

  it('选择项目后按 API 契约传递待询价统计参数', async () => {
    const wrapper = mount(BOMList)
    await flushPromises()
    getBOMPendingQuoteCount.mockClear()

    ;(wrapper.vm as any).selectedProject = 1
    await flushPromises()

    expect(getBOMPendingQuoteCount).toHaveBeenCalledWith({ project: 1 })
  })
})
