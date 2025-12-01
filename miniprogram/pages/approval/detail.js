/**
 * 审批详情页面
 */
const app = getApp()

Page({
  data: {
    id: null,
    type: 'task', // task 或 instance
    detail: {},
    tasks: [],
    comment: '',
    canApprove: false,
    canWithdraw: false,
    approving: false,
    rejecting: false,
    withdrawing: false,
    statusClass: '',
    statusIcon: '⏳',
    amountDisplay: '0.00',
    submitTimeDisplay: ''
  },

  onLoad(options) {
    this.setData({
      id: options.id,
      type: options.type || 'task'
    })
    this.loadDetail()
  },

  async loadDetail() {
    try {
      let detail, tasks = []

      if (this.data.type === 'task') {
        // 从任务加载
        const taskRes = await app.request({ 
          url: `/core/workflow/tasks/${this.data.id}/` 
        })
        
        // 获取实例详情
        const instanceRes = await app.request({ 
          url: `/core/workflow/instances/${taskRes.instance}/` 
        })
        
        detail = {
          ...instanceRes,
          step_name: taskRes.step_name,
          task_id: taskRes.id
        }
        tasks = instanceRes.tasks || []
        
      } else {
        // 从实例加载
        detail = await app.request({ 
          url: `/core/workflow/instances/${this.data.id}/` 
        })
        tasks = detail.tasks || []
      }

      // 处理任务显示
      tasks = tasks.map(task => ({
        ...task,
        action_time_display: app.formatDateTime(task.action_time)
      }))

      // 判断权限
      const userInfo = app.globalData.userInfo
      const canApprove = this.data.type === 'task' && detail.status === 'PENDING'
      const canWithdraw = detail.status === 'PENDING' && 
                          detail.submitter === userInfo?.id

      // 状态样式
      let statusClass = 'pending'
      let statusIcon = '⏳'
      if (detail.status === 'APPROVED') {
        statusClass = 'approved'
        statusIcon = '✅'
      } else if (detail.status === 'REJECTED') {
        statusClass = 'rejected'
        statusIcon = '❌'
      } else if (detail.status === 'WITHDRAWN') {
        statusClass = 'withdrawn'
        statusIcon = '↩️'
      }

      this.setData({
        detail,
        tasks,
        canApprove,
        canWithdraw,
        statusClass,
        statusIcon,
        amountDisplay: app.formatMoney(detail.amount),
        submitTimeDisplay: app.formatDateTime(detail.submit_time)
      })

    } catch (err) {
      console.error('加载详情失败:', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onCommentInput(e) {
    this.setData({ comment: e.detail.value })
  },

  async handleApprove() {
    wx.showModal({
      title: '确认通过',
      content: '确定要通过此审批吗？',
      success: async (res) => {
        if (res.confirm) {
          this.setData({ approving: true })
          try {
            await app.request({
              url: `/core/workflow/tasks/${this.data.detail.task_id}/approve/`,
              method: 'POST',
              data: { comment: this.data.comment }
            })
            wx.showToast({ title: '审批通过', icon: 'success' })
            setTimeout(() => {
              wx.navigateBack()
            }, 1500)
          } catch (err) {
            wx.showToast({ 
              title: err.error || '操作失败', 
              icon: 'none' 
            })
          } finally {
            this.setData({ approving: false })
          }
        }
      }
    })
  },

  async handleReject() {
    if (!this.data.comment.trim()) {
      wx.showToast({ title: '请填写拒绝原因', icon: 'none' })
      return
    }

    wx.showModal({
      title: '确认拒绝',
      content: '确定要拒绝此审批吗？',
      success: async (res) => {
        if (res.confirm) {
          this.setData({ rejecting: true })
          try {
            await app.request({
              url: `/core/workflow/tasks/${this.data.detail.task_id}/reject/`,
              method: 'POST',
              data: { comment: this.data.comment }
            })
            wx.showToast({ title: '已拒绝', icon: 'success' })
            setTimeout(() => {
              wx.navigateBack()
            }, 1500)
          } catch (err) {
            wx.showToast({ 
              title: err.error || '操作失败', 
              icon: 'none' 
            })
          } finally {
            this.setData({ rejecting: false })
          }
        }
      }
    })
  },

  async handleWithdraw() {
    wx.showModal({
      title: '确认撤回',
      content: '确定要撤回此申请吗？',
      success: async (res) => {
        if (res.confirm) {
          this.setData({ withdrawing: true })
          try {
            await app.request({
              url: `/core/workflow/instances/${this.data.id}/withdraw/`,
              method: 'POST'
            })
            wx.showToast({ title: '已撤回', icon: 'success' })
            setTimeout(() => {
              wx.navigateBack()
            }, 1500)
          } catch (err) {
            wx.showToast({ 
              title: err.error || '操作失败', 
              icon: 'none' 
            })
          } finally {
            this.setData({ withdrawing: false })
          }
        }
      }
    })
  }
})
