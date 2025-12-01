/**
 * 项目列表页面
 */
const app = getApp()

Page({
  data: {
    projects: [],
    keyword: '',
    currentStatus: '',
    statusList: [
      { value: '', label: '全部' },
      { value: 'ACTIVE', label: '进行中' },
      { value: 'DRAFT', label: '草稿' },
      { value: 'PAUSED', label: '暂停' },
      { value: 'COMPLETED', label: '已完成' }
    ],
    loading: false,
    noMore: false,
    page: 1
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadProjects(true)
  },

  onSearchInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  doSearch() {
    this.loadProjects(true)
  },

  filterByStatus(e) {
    const status = e.currentTarget.dataset.status
    this.setData({ currentStatus: status })
    this.loadProjects(true)
  },

  async loadProjects(reset = false) {
    if (reset) {
      this.setData({ page: 1, noMore: false, projects: [] })
    }

    if (this.data.noMore || this.data.loading) return

    this.setData({ loading: true })

    try {
      const params = {
        page: this.data.page,
        page_size: 10
      }

      if (this.data.keyword) {
        params.search = this.data.keyword
      }

      if (this.data.currentStatus) {
        params.status = this.data.currentStatus
      }

      const res = await app.request({
        url: '/projects/',
        data: params
      })

      const list = (res.results || []).map(item => ({
        ...item,
        budget_display: app.formatMoney(item.budget_total),
        statusClass: this.getStatusClass(item.status)
      }))

      // 加载每个项目的任务进度
      for (let project of list) {
        try {
          const summary = await app.request({
            url: `/projects/${project.id}/summary/`,
            showLoading: false
          })
          project.task_progress = summary.task_stats?.progress || 0
        } catch (e) {
          project.task_progress = 0
        }
      }

      this.setData({
        projects: reset ? list : [...this.data.projects, ...list],
        page: this.data.page + 1,
        noMore: list.length < 10
      })

    } catch (err) {
      console.error('加载项目失败:', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  getStatusClass(status) {
    const classMap = {
      'DRAFT': 'tag-info',
      'ACTIVE': 'tag-success',
      'PAUSED': 'tag-warning',
      'COMPLETED': 'tag-info',
      'ARCHIVED': 'tag-info'
    }
    return classMap[status] || 'tag-info'
  },

  goToDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/project/detail?id=${id}` })
  },

  onPullDownRefresh() {
    this.loadProjects(true).finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    this.loadProjects()
  }
})
