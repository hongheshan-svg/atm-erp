/**
 * 首页 - 工作台
 */
const app = getApp()

Page({
  data: {
    userInfo: {},
    today: '',
    pendingCount: 0,
    submittedCount: 0,
    projectCount: 0,
    pendingTasks: []
  },

  onLoad() {
    this.setToday()
  },

  onShow() {
    if (!app.checkLogin()) return
    this.setData({ userInfo: app.globalData.userInfo || {} })
    this.loadData()
  },

  setToday() {
    const now = new Date()
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    const today = `${now.getMonth() + 1}月${now.getDate()}日 ${weekDays[now.getDay()]}`
    this.setData({ today })
  },

  async loadData() {
    try {
      // 并行加载数据
      const [tasksRes, statsRes] = await Promise.all([
        app.request({ url: '/core/workflow/tasks/my_pending/', showLoading: false }),
        app.request({ url: '/core/workflow/tasks/pending_count/', showLoading: false })
      ])

      // 处理待办任务
      const pendingTasks = (tasksRes.slice ? tasksRes : tasksRes.results || []).slice(0, 5).map(task => ({
        ...task,
        amount_display: app.formatMoney(task.amount),
        created_at_display: app.formatDateTime(task.created_at)
      }))

      this.setData({
        pendingTasks,
        pendingCount: statsRes.count || 0
      })

      // 加载项目统计
      this.loadProjectStats()

    } catch (err) {
      console.error('加载数据失败:', err)
    }
  },

  async loadProjectStats() {
    try {
      const res = await app.request({ 
        url: '/projects/?status=ACTIVE&page_size=1', 
        showLoading: false 
      })
      this.setData({ projectCount: res.count || 0 })
    } catch (err) {
      console.error('加载项目统计失败:', err)
    }
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.loadData().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 导航方法
  goToApproval() {
    wx.switchTab({ url: '/pages/approval/list' })
  },

  goToProject() {
    wx.switchTab({ url: '/pages/project/list' })
  },

  goToDashboard() {
    wx.navigateTo({ url: '/pages/dashboard/dashboard' })
  },

  goToMySubmit() {
    wx.navigateTo({ url: '/pages/approval/list?tab=submitted' })
  },

  goToDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/approval/detail?id=${id}` })
  }
})
