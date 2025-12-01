/**
 * ERP微信小程序 - 移动审批与数据查看
 */
App({
  globalData: {
    userInfo: null,
    token: null,
    baseUrl: 'https://your-erp-domain.com/api', // 替换为实际API地址
  },

  onLaunch() {
    // 检查登录状态
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.globalData.userInfo = wx.getStorageSync('userInfo')
    }
  },

  // 检查是否登录
  checkLogin() {
    if (!this.globalData.token) {
      wx.redirectTo({ url: '/pages/login/login' })
      return false
    }
    return true
  },

  // 统一请求方法
  request(options) {
    const { url, method = 'GET', data = {}, showLoading = true } = options
    
    return new Promise((resolve, reject) => {
      if (showLoading) {
        wx.showLoading({ title: '加载中...' })
      }

      wx.request({
        url: `${this.globalData.baseUrl}${url}`,
        method,
        data,
        header: {
          'Content-Type': 'application/json',
          'Authorization': this.globalData.token ? `Bearer ${this.globalData.token}` : ''
        },
        success: (res) => {
          if (showLoading) wx.hideLoading()
          
          if (res.statusCode === 200 || res.statusCode === 201) {
            resolve(res.data)
          } else if (res.statusCode === 401) {
            // Token过期，跳转登录
            wx.removeStorageSync('token')
            wx.removeStorageSync('userInfo')
            this.globalData.token = null
            this.globalData.userInfo = null
            wx.redirectTo({ url: '/pages/login/login' })
            reject(new Error('登录已过期'))
          } else {
            reject(res.data)
          }
        },
        fail: (err) => {
          if (showLoading) wx.hideLoading()
          wx.showToast({ title: '网络错误', icon: 'none' })
          reject(err)
        }
      })
    })
  },

  // 格式化金额
  formatMoney(amount) {
    if (!amount) return '0.00'
    return Number(amount).toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })
  },

  // 格式化日期
  formatDate(dateStr) {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  },

  // 格式化日期时间
  formatDateTime(dateStr) {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  }
})
