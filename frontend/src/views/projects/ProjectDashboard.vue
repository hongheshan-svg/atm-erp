<template>
  <div class="dashboard-container">
    <!-- 项目选择器 -->
    <el-card class="project-selector" shadow="never">
      <el-select v-model="selectedProjectId" placeholder="选择项目" size="large" filterable style="width: 400px;" @change="loadDashboard">
        <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
      </el-select>
      <el-button type="primary" size="large" @click="loadDashboard" :loading="loading" style="margin-left: 10px;">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </el-card>
    
    <template v-if="dashboard">
      <!-- 基本信息和状态 -->
      <el-row :gutter="20">
        <el-col :span="16">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span>{{ dashboard.basic_info.code }} - {{ dashboard.basic_info.name }}</span>
                <el-tag :type="getStatusType(dashboard.basic_info.status)" size="large">
                  {{ getStatusName(dashboard.basic_info.status) }}
                </el-tag>
              </div>
            </template>
            <el-descriptions :column="4" border>
              <el-descriptions-item label="客户">{{ dashboard.basic_info.customer_name }}</el-descriptions-item>
              <el-descriptions-item label="项目经理">{{ dashboard.basic_info.manager_name }}</el-descriptions-item>
              <el-descriptions-item label="开始日期">{{ dashboard.basic_info.start_date }}</el-descriptions-item>
              <el-descriptions-item label="结束日期">{{ dashboard.basic_info.end_date }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
        <el-col :span="8">
          <!-- 预警信息 -->
          <el-card shadow="hover" v-if="dashboard.alerts && dashboard.alerts.length > 0">
            <template #header>
              <span><el-icon><WarningFilled /></el-icon> 预警提醒</span>
            </template>
            <div v-for="(alert, index) in dashboard.alerts" :key="index" class="alert-item">
              <el-alert
                :title="alert.message"
                :type="alert.severity === 'HIGH' ? 'error' : 'warning'"
                :closable="false"
                show-icon
                style="margin-bottom: 10px;"
              />
            </div>
          </el-card>
          <el-card shadow="hover" v-else>
            <template #header>
              <span><el-icon><SuccessFilled /></el-icon> 项目状态</span>
            </template>
            <el-result icon="success" title="运行正常" sub-title="暂无预警信息" />
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 进度和工时 -->
      <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>任务进度</template>
            <div class="progress-card">
              <el-progress type="dashboard" :percentage="dashboard.progress.progress_percent" :width="150" :stroke-width="15">
                <template #default>
                  <span class="percentage-value">{{ dashboard.progress.progress_percent }}%</span>
                  <span class="percentage-label">完成率</span>
                </template>
              </el-progress>
              <div class="progress-stats">
                <div class="stat-item">
                  <span class="stat-value">{{ dashboard.progress.total_tasks }}</span>
                  <span class="stat-label">总任务</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value text-success">{{ dashboard.progress.completed_tasks }}</span>
                  <span class="stat-label">已完成</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value text-warning">{{ dashboard.progress.in_progress_tasks }}</span>
                  <span class="stat-label">进行中</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value text-info">{{ dashboard.progress.pending_tasks }}</span>
                  <span class="stat-label">待办</span>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>工时统计</template>
            <div class="time-stats">
              <el-statistic title="计划工时" :value="dashboard.time.planned_hours" suffix="小时" />
              <el-divider />
              <el-statistic title="实际工时" :value="dashboard.time.actual_hours" suffix="小时" />
              <el-divider />
              <el-progress 
                :percentage="Math.min(dashboard.time.hours_utilization, 100)" 
                :status="dashboard.time.hours_utilization > 100 ? 'exception' : 'success'"
              >
                <span>工时使用率 {{ dashboard.time.hours_utilization }}%</span>
              </el-progress>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>预算使用</template>
            <div class="budget-stats">
              <el-statistic title="总预算" :value="dashboard.budget.budget_total" :precision="2" prefix="¥" />
              <el-divider />
              <el-statistic title="实际支出" :value="dashboard.budget.actual_total" :precision="2" prefix="¥" />
              <el-divider />
              <el-progress 
                :percentage="Math.min(dashboard.budget.budget_utilization, 100)"
                :status="dashboard.budget.budget_utilization > 90 ? 'exception' : 'success'"
              >
                <span>预算使用率 {{ dashboard.budget.budget_utilization }}%</span>
              </el-progress>
              <div class="variance" :class="dashboard.budget.budget_variance >= 0 ? 'positive' : 'negative'">
                {{ dashboard.budget.budget_variance >= 0 ? '节余' : '超支' }}: ¥{{ Math.abs(dashboard.budget.budget_variance).toFixed(2) }}
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 财务和采购 -->
      <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>财务概况</template>
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="finance-section">
                  <h4>应收账款</h4>
                  <el-statistic title="总应收" :value="dashboard.finance.total_receivable" :precision="2" prefix="¥" />
                  <el-statistic title="已收款" :value="dashboard.finance.received" :precision="2" prefix="¥" :value-style="{ color: '#67c23a' }" />
                  <el-statistic title="待收款" :value="dashboard.finance.pending_receivable" :precision="2" prefix="¥" :value-style="{ color: '#e6a23c' }" />
                </div>
              </el-col>
              <el-col :span="12">
                <div class="finance-section">
                  <h4>应付账款</h4>
                  <el-statistic title="总应付" :value="dashboard.finance.total_payable" :precision="2" prefix="¥" />
                  <el-statistic title="已付款" :value="dashboard.finance.paid" :precision="2" prefix="¥" :value-style="{ color: '#67c23a' }" />
                  <el-statistic title="待付款" :value="dashboard.finance.pending_payable" :precision="2" prefix="¥" :value-style="{ color: '#e6a23c' }" />
                </div>
              </el-col>
            </el-row>
            <el-divider />
            <div class="cash-flow" :class="dashboard.finance.cash_flow >= 0 ? 'positive' : 'negative'">
              现金流: ¥{{ dashboard.finance.cash_flow.toFixed(2) }}
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>采购与生产</template>
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="purchase-section">
                  <h4>采购订单</h4>
                  <div class="stat-row">
                    <span>总订单:</span>
                    <span>{{ dashboard.purchase.total_orders }}</span>
                  </div>
                  <div class="stat-row">
                    <span>待交付:</span>
                    <span class="text-warning">{{ dashboard.purchase.pending_orders }}</span>
                  </div>
                  <div class="stat-row">
                    <span>在途中:</span>
                    <span class="text-primary">{{ dashboard.purchase.in_delivery }}</span>
                  </div>
                  <div class="stat-row">
                    <span>已完成:</span>
                    <span class="text-success">{{ dashboard.purchase.completed_orders }}</span>
                  </div>
                  <div class="stat-row">
                    <span>采购总额:</span>
                    <span>¥{{ dashboard.purchase.total_amount.toFixed(2) }}</span>
                  </div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="production-section">
                  <h4>生产计划</h4>
                  <div class="stat-row">
                    <span>总计划:</span>
                    <span>{{ dashboard.production.total_plans }}</span>
                  </div>
                  <div class="stat-row">
                    <span>进行中:</span>
                    <span class="text-warning">{{ dashboard.production.in_progress }}</span>
                  </div>
                  <div class="stat-row">
                    <span>已完成:</span>
                    <span class="text-success">{{ dashboard.production.completed }}</span>
                  </div>
                </div>
              </el-col>
            </el-row>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- BOM成本 -->
      <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="24">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span>BOM成本分析</span>
                <el-button type="primary" link @click="loadBOMCost">
                  <el-icon><View /></el-icon> 查看详情
                </el-button>
              </div>
            </template>
            <el-row :gutter="40">
              <el-col :span="6">
                <el-statistic title="BOM物料数" :value="dashboard.bom.total_items" suffix="项" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="预估成本" :value="dashboard.bom.estimated_cost" :precision="2" prefix="¥" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="材料预算" :value="dashboard.budget.budget_material" :precision="2" prefix="¥" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="实际材料成本" :value="dashboard.budget.actual_material_cost" :precision="2" prefix="¥" />
              </el-col>
            </el-row>
          </el-card>
        </el-col>
      </el-row>
    </template>
    
    <el-empty v-else-if="!loading" description="请选择一个项目查看仪表盘" />
    <!-- BOM成本详情 -->
    <el-dialog v-model="bomDialogVisible" title="BOM成本详情" width="800px">
      <el-table :data="bomItems" v-loading="bomLoading" stripe max-height="500">
        <el-table-column prop="material_code" label="物料编码" width="120" />
        <el-table-column prop="material_name" label="物料名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="specification" label="规格" width="120" />
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column label="单价" width="100" align="right">
          <template #default="{ row }">¥{{ row.unit_price?.toLocaleString() || 0 }}</template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">¥{{ (row.amount || (row.quantity * row.unit_price) || 0).toLocaleString() }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!bomLoading && bomItems.length === 0" description="暂无BOM数据" />
      <template #footer>
        <el-button @click="bomDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, WarningFilled, SuccessFilled, View } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const projects = ref([])
const selectedProjectId = ref(null)
const dashboard = ref(null)
const bomDialogVisible = ref(false)
const bomItems = ref([])
const bomLoading = ref(false)

const statusMap = {
  'DRAFT': '草稿',
  'PLANNING': '规划中',
  'PENDING': '审批中',
  'REJECTED': '已拒绝',
  'IN_PROGRESS': '进行中',
  'ACTIVE': '进行中',
  'PAUSED': '暂停',
  'COMPLETED': '已完成',
  'CANCELLED': '已取消',
  'ARCHIVED': '已归档',
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PLANNING': 'info',
    'PENDING': 'warning',
    'REJECTED': 'danger',
    'IN_PROGRESS': 'primary',
    'ACTIVE': 'primary',
    'PAUSED': 'warning',
    'COMPLETED': 'success',
    'CANCELLED': 'danger',
    'ARCHIVED': 'info',
  }
  return types[status] || 'info'
}

const getStatusName = (status) => statusMap[status] || status

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    projects.value = res.results || res
    
    // 自动选择第一个进行中的项目
    const activeProject = projects.value.find(p => ['IN_PROGRESS', 'ACTIVE'].includes(p.status))
    if (activeProject) {
      selectedProjectId.value = activeProject.id
      loadDashboard()
    }
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadDashboard = async () => {
  if (!selectedProjectId.value) return
  
  try {
    loading.value = true
    const res = await request.get(`/projects/dashboard/${selectedProjectId.value}/`)
    dashboard.value = res
  } catch (error) {
    console.error('加载仪表盘失败:', error)
    ElMessage.error('加载仪表盘失败')
  } finally {
    loading.value = false
  }
}

const loadBOMCost = async () => {
  if (!selectedProjectId.value) return
  bomDialogVisible.value = true
  bomLoading.value = true
  try {
    const res = await request.get(`/projects/projects/${selectedProjectId.value}/bom-items/`)
    bomItems.value = res.data?.results || res.results || res.data || []
  } catch {
    bomItems.value = []
  } finally {
    bomLoading.value = false
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}

.project-selector {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-card {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.percentage-value {
  font-size: 24px;
  font-weight: bold;
}

.percentage-label {
  font-size: 12px;
  color: #999;
}

.progress-stats {
  display: flex;
  gap: 20px;
  margin-top: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 20px;
  font-weight: bold;
}

.stat-label {
  font-size: 12px;
  color: #999;
}

.text-success { color: #67c23a; }
.text-warning { color: #e6a23c; }
.text-danger { color: #f56c6c; }
.text-info { color: #909399; }
.text-primary { color: #409eff; }

.time-stats, .budget-stats {
  text-align: center;
}

.variance {
  margin-top: 15px;
  font-size: 16px;
  font-weight: bold;
  text-align: center;
}

.variance.positive { color: #67c23a; }
.variance.negative { color: #f56c6c; }

.finance-section, .purchase-section, .production-section {
  padding: 10px;
}

.finance-section h4, .purchase-section h4, .production-section h4 {
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.cash-flow {
  font-size: 18px;
  font-weight: bold;
  text-align: center;
}

.cash-flow.positive { color: #67c23a; }
.cash-flow.negative { color: #f56c6c; }

.alert-item {
  margin-bottom: 10px;
}
</style>
