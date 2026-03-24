Page({
  data: {
    taskList: [],
    currentTask: null,
    reportForm: { quantity: '', hours: '', notes: '' },
    loading: false
  },
  onLoad() { this.loadTasks() },
  loadTasks() {
    this.setData({ loading: true })
    wx.request({
      url: getApp().globalData.baseUrl + '/api/production/work-orders/',
      header: { Authorization: 'Bearer ' + wx.getStorageSync('token') },
      success: (res) => { this.setData({ taskList: res.data.results || [] }) },
      complete: () => { this.setData({ loading: false }) }
    })
  },
  selectTask(e) { this.setData({ currentTask: e.currentTarget.dataset.task }) },
  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ ['reportForm.' + field]: e.detail.value })
  },
  submitReport() {
    const { currentTask, reportForm } = this.data
    if (!currentTask) { wx.showToast({ title: '请选择工单', icon: 'none' }); return }
    wx.request({
      url: getApp().globalData.baseUrl + '/api/production/work-reports/',
      method: 'POST',
      header: { Authorization: 'Bearer ' + wx.getStorageSync('token'), 'Content-Type': 'application/json' },
      data: { work_order: currentTask.id, ...reportForm },
      success: () => { wx.showToast({ title: '报工成功' }); this.setData({ reportForm: { quantity: '', hours: '', notes: '' }, currentTask: null }) },
      fail: () => { wx.showToast({ title: '提交失败', icon: 'none' }) }
    })
  }
})
