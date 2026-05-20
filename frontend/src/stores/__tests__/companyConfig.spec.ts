import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useCompanyConfig, loadCompanyConfig } from '../companyConfig'

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  }
}))

describe('companyConfig store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset loaded state
    const { loaded, companyName, companyShortName } = useCompanyConfig()
    loaded.value = false
    companyName.value = ''
    companyShortName.value = ''
  })

  describe('useCompanyConfig', () => {
    it('returns reactive refs', () => {
      const config = useCompanyConfig()

      expect(config.companyName.value).toBe('')
      expect(config.companyShortName.value).toBe('')
      expect(config.loaded.value).toBe(false)
    })
  })

  describe('loadCompanyConfig', () => {
    it('fetches and stores company config', async () => {
      const request = await import('@/utils/request')
      ;(request.default.get as any).mockResolvedValue({
        company_name: '测试公司',
        company_short_name: '测试',
      })

      await loadCompanyConfig()

      const { companyName, companyShortName, loaded } = useCompanyConfig()
      expect(companyName.value).toBe('测试公司')
      expect(companyShortName.value).toBe('测试')
      expect(loaded.value).toBe(true)
    })

    it('does not fetch if already loaded', async () => {
      const { loaded } = useCompanyConfig()
      loaded.value = true

      const request = await import('@/utils/request')
      await loadCompanyConfig()

      expect(request.default.get).not.toHaveBeenCalled()
    })

    it('handles fetch error gracefully', async () => {
      const request = await import('@/utils/request')
      ;(request.default.get as any).mockRejectedValue(new Error('Network error'))

      await loadCompanyConfig()

      const { companyName, loaded } = useCompanyConfig()
      expect(companyName.value).toBe('')
      expect(loaded.value).toBe(false)
    })
  })
})
