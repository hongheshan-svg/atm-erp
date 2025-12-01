/**
 * 数据看板页面
 */
const app = getApp()

Page({
  data: {
    today: '',
    financial: {
      revenue: '0.00',
      purchases: '0.00',
      receivables: '0.00',
      payables: '0.00'
    },
    projects: {
      active_projects: 0,
      completed_tasks: 0,
      task_completion_rate: 0
    },
    inventory: {
      inventory_value: '0.00',
      low_stock_items: 0,
      recent_movements: 0
    },
    cashflow: {
      expected_inflows: '0.00',
      expected_outflows: '0.00',
      net_cash_flow: '0.00'
    }
  },

  onLoad() {
    this.setToday()
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadDashboardData()
  },

  setToday() {
    const now = new Date()
    const today = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`
    this.setData({ today })
  },

  async loadDashboardData() {
    wx.showLoading({ title: '加载中...' })

    try {
      // 并行加载所有数据
      const [kpiRes, cashflowRes] = await Promise.all([
        app.request({ url: '/analytics/dashboard/kpis/', showLoading: false }),
        app.request({ url: '/analytics/dashboard/cash-flow-forecast/', showLoading: false })
      ])

      // 处理财务数据
      const financial = kpiRes.financial || {}
      this.setData({
        financial: {
          revenue: app.formatMoney(financial.revenue?.total || 0),
          purchases: app.formatMoney(financial.purchases?.total || 0),
          receivables: app.formatMoney(financial.receivables || 0),
          payables: app.formatMoney(financial.payables || 0)
        }
      })

      // 处理项目数据
      const projects = kpiRes.projects || {}
      this.setData({
        projects: {
          active_projects: projects.active_projects || 0,
          completed_tasks: projects.completed_tasks || 0,
          task_completion_rate: Math.round(projects.task_completion_rate || 0)
        }
      })

      // 处理库存数据
      const inventory = kpiRes.inventory || {}
      this.setData({
        inventory: {
          inventory_value: app.formatMoney(inventory.inventory_value || 0),
          low_stock_items: inventory.low_stock_items || 0,
          recent_movements: inventory.recent_movements || 0
        }
      })

      // 处理现金流预测
      this.setData({
        cashflow: {
          expected_inflows: app.formatMoney(cashflowRes.expected_inflows || 0),
          expected_outflows: app.formatMoney(cashflowRes.expected_outflows || 0),
          net_cash_flow: app.formatMoney(cashflowRes.net_cash_flow || 0)
        }
      })

    } catch (err) {
      console.error('加载看板数据失败:', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  onPullDownRefresh() {
    this.loadDashboardData().finally(() => {
      wx.stopPullDownRefresh()
    })
  }
})
