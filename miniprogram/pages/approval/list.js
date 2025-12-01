/**
 * 审批列表页面
 */
const app = getApp()

Page({
  data: {
    currentTab: 'pending',
    pendingList: [],
    submittedList: [],
    pendingCount: 0,
    loading: false,
    noMore: false
  },

  onLoad(options) {
    if (options.tab) {
      this.setData({ currentTab: options.tab })
    }
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadData()
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ 
      currentTab: tab,
      noMore: false
    })
    this.loadData()
  },

  async loadData() {
    this.setData({ loading: true })

    try {
      if (this.data.currentTab === 'pending') {
        await this.loadPendingList()
      } else {
        await this.loadSubmittedList()
      }
    } catch (err) {
      console.error('加载失败:', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadPendingList() {
    const [tasksRes, countRes] = await Promise.all([
      app.request({ url: '/core/workflow/tasks/my_pending/' }),
      app.request({ url: '/core/workflow/tasks/pending_count/', showLoading: false })
    ])

    const list = (tasksRes.slice ? tasksRes : tasksRes.results || []).map(item => ({
      ...item,
      amount_display: app.formatMoney(item.amount),
      created_at_display: app.formatDateTime(item.created_at)
    }))

    this.setData({
      pendingList: list,
      pendingCount: countRes.count || 0,
      noMore: true
    })
  },

  async loadSubmittedList() {
    const res = await app.request({ url: '/core/workflow/instances/my_submitted/' })

    const list = (res.slice ? res : res.results || []).map(item => ({
      ...item,
      amount_display: app.formatMoney(item.amount),
      submit_time_display: app.formatDateTime(item.submit_time),
      progress: item.total_steps > 0 
        ? Math.round((item.current_step - 1) / item.total_steps * 100) 
        : 0
    }))

    this.setData({
      submittedList: list,
      noMore: true
    })
  },

  goToDetail(e) {
    const { id, type } = e.currentTarget.dataset
    wx.navigateTo({ 
      url: `/pages/approval/detail?id=${id}&type=${type}` 
    })
  },

  onPullDownRefresh() {
    this.loadData().finally(() => {
      wx.stopPullDownRefresh()
    })
  }
})
