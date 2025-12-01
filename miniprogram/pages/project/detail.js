/**
 * 项目详情页面
 */
const app = getApp()

Page({
  data: {
    id: null,
    project: {},
    taskStats: { total: 0, completed: 0, progress: 0 },
    memberStats: { count: 0 },
    bomStats: { count: 0 },
    statusClass: '',
    budgetDisplay: '0.00',
    materialBudget: '0.00',
    laborBudget: '0.00',
    expenseBudget: '0.00',
    materialPercent: 0,
    laborPercent: 0,
    expensePercent: 0
  },

  onLoad(options) {
    this.setData({ id: options.id })
    this.loadDetail()
  },

  async loadDetail() {
    try {
      // 加载项目详情和统计
      const [projectRes, summaryRes] = await Promise.all([
        app.request({ url: `/projects/${this.data.id}/` }),
        app.request({ url: `/projects/${this.data.id}/summary/` })
      ])

      const project = {
        ...projectRes,
        budget_material_display: app.formatMoney(projectRes.budget_material),
        budget_labor_display: app.formatMoney(projectRes.budget_labor),
        budget_expense_display: app.formatMoney(projectRes.budget_expense)
      }

      // 加载预算使用情况
      let budgetSummary = { material: {}, labor: {}, expense: {} }
      try {
        budgetSummary = await app.request({
          url: '/purchase/requests/project_budget_summary/',
          data: { project_id: this.data.id },
          showLoading: false
        })
      } catch (e) {
        console.log('预算数据加载失败')
      }

      // 计算预算使用百分比
      const materialUsed = budgetSummary.material?.used || 0
      const laborUsed = budgetSummary.labor?.used || 0
      const expenseUsed = budgetSummary.expense?.used || 0

      const materialPercent = project.budget_material > 0 
        ? Math.min(100, (materialUsed / project.budget_material) * 100) 
        : 0
      const laborPercent = project.budget_labor > 0 
        ? Math.min(100, (laborUsed / project.budget_labor) * 100) 
        : 0
      const expensePercent = project.budget_expense > 0 
        ? Math.min(100, (expenseUsed / project.budget_expense) * 100) 
        : 0

      this.setData({
        project,
        taskStats: summaryRes.task_stats || {},
        memberStats: summaryRes.member_stats || {},
        bomStats: summaryRes.bom_stats || {},
        statusClass: this.getStatusClass(project.status),
        budgetDisplay: app.formatMoney(project.budget_total),
        materialBudget: app.formatMoney(materialUsed),
        laborBudget: app.formatMoney(laborUsed),
        expenseBudget: app.formatMoney(expenseUsed),
        materialPercent: Math.round(materialPercent),
        laborPercent: Math.round(laborPercent),
        expensePercent: Math.round(expensePercent)
      })

    } catch (err) {
      console.error('加载项目详情失败:', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
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

  onPullDownRefresh() {
    this.loadDetail().finally(() => {
      wx.stopPullDownRefresh()
    })
  }
})
