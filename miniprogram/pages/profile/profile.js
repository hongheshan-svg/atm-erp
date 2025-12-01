/**
 * 个人中心页面
 */
const app = getApp()

Page({
  data: {
    userInfo: {},
    pendingCount: 0,
    submittedCount: 0,
    myProjectCount: 0
  },

  onShow() {
    if (!app.checkLogin()) return
    this.setData({ userInfo: app.globalData.userInfo || {} })
    this.loadStats()
  },

  async loadStats() {
    try {
      // 加载待审批数量
      const countRes = await app.request({
        url: '/core/workflow/tasks/pending_count/',
        showLoading: false
      })
      this.setData({ pendingCount: countRes.count || 0 })

      // 加载我提交的数量
      const submittedRes = await app.request({
        url: '/core/workflow/instances/my_submitted/',
        showLoading: false
      })
      this.setData({ 
        submittedCount: (submittedRes.slice ? submittedRes : submittedRes.results || []).length 
      })

    } catch (err) {
      console.error('加载统计失败:', err)
    }
  },

  goToApproval() {
    wx.switchTab({ url: '/pages/approval/list' })
  },

  goToMySubmit() {
    wx.navigateTo({ url: '/pages/approval/list?tab=submitted' })
  },

  goToProject() {
    wx.switchTab({ url: '/pages/project/list' })
  },

  goToDashboard() {
    wx.navigateTo({ url: '/pages/dashboard/dashboard' })
  },

  showAbout() {
    wx.showModal({
      title: '关于',
      content: 'ERP移动审批系统\n版本: 1.0.0\n\n支持功能:\n- 移动审批\n- 项目查看\n- 数据看板',
      showCancel: false
    })
  },

  clearCache() {
    wx.showModal({
      title: '确认',
      content: '确定要清除缓存吗？',
      success: (res) => {
        if (res.confirm) {
          wx.clearStorageSync()
          // 保留登录信息
          if (app.globalData.token) {
            wx.setStorageSync('token', app.globalData.token)
            wx.setStorageSync('userInfo', app.globalData.userInfo)
          }
          wx.showToast({ title: '缓存已清除', icon: 'success' })
        }
      }
    })
  },

  handleLogout() {
    wx.showModal({
      title: '确认退出',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          // 清除登录信息
          wx.removeStorageSync('token')
          wx.removeStorageSync('refreshToken')
          wx.removeStorageSync('userInfo')
          app.globalData.token = null
          app.globalData.userInfo = null

          wx.showToast({ title: '已退出', icon: 'success' })

          setTimeout(() => {
            wx.redirectTo({ url: '/pages/login/login' })
          }, 1000)
        }
      }
    })
  }
})
