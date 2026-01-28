<template>
  <div class="crm-dashboard">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-leads">
          <div class="stat-icon"><el-icon><User /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.leads_count || 0 }}</div>
            <div class="stat-label">销售线索</div>
            <div class="stat-trend" :class="stats.leads_trend >= 0 ? 'up' : 'down'">
              <span v-if="stats.leads_trend >= 0">↑</span><span v-else>↓</span>
              {{ Math.abs(stats.leads_trend || 0) }}% 较上月
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-opportunities">
          <div class="stat-icon"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.opportunities_count || 0 }}</div>
            <div class="stat-label">进行中商机</div>
            <div class="stat-amount">预计 ¥{{ formatNumber(stats.opportunities_amount) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-customers">
          <div class="stat-icon"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.customers_count || 0 }}</div>
            <div class="stat-label">活跃客户</div>
            <div class="stat-sub">本月新增 {{ stats.new_customers || 0 }} 家</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-won">
          <div class="stat-icon"><el-icon><Trophy /></el-icon></div>
          <div class="stat-content">
            <div class="stat-value">¥{{ formatNumber(stats.won_amount) }}</div>
            <div class="stat-label">本月成交</div>
            <div class="stat-sub">{{ stats.won_count || 0 }} 单</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主要内容区 -->
    <el-row :gutter="16" class="main-content">
      <!-- 左侧：销售漏斗和商机阶段 -->
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>商机阶段分布</span>
              <el-button type="primary" link @click="$router.push('/sales/opportunities')">查看全部</el-button>
            </div>
          </template>
          <div class="pipeline-stages">
            <div v-for="stage in pipelineStages" :key="stage.stage" class="pipeline-stage">
              <div class="stage-header" :style="{ borderLeftColor: getStageColor(stage.stage) }">
                <span class="stage-name">{{ stage.stage_name }}</span>
                <el-tag size="small">{{ stage.count }} 个</el-tag>
              </div>
              <div class="stage-amount">¥{{ formatNumber(stage.amount) }}</div>
              <div class="stage-bar">
                <div class="stage-bar-fill" :style="{ width: getStagePercent(stage.amount) + '%', background: getStageColor(stage.stage) }"></div>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 近期商机 -->
        <el-card shadow="never" class="section-card" style="margin-top: 16px;">
          <template #header>
            <div class="card-header">
              <span>近期商机动态</span>
            </div>
          </template>
          <el-table :data="recentOpportunities" border stripe max-height="300" size="small" table-layout="auto">
            <el-table-column prop="opportunity_no" label="编号" min-width="110" show-overflow-tooltip />
            <el-table-column prop="name" label="商机名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="customer_name" label="客户" min-width="120" show-overflow-tooltip />
            <el-table-column prop="stage_display" label="阶段" min-width="80">
              <template #default="{ row }">
                <el-tag :type="getStageType(row.stage)" size="small">{{ row.stage_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="金额" min-width="100" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.estimated_amount) }}</template>
            </el-table-column>
            <el-table-column prop="expected_close_date" label="预计成交" min-width="90" />
          </el-table>
        </el-card>
      </el-col>

      <!-- 右侧：待办和快捷操作 -->
      <el-col :span="8">
        <!-- 今日待办 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>今日待办</span>
              <el-badge :value="todayTasks.length" :hidden="!todayTasks.length" />
            </div>
          </template>
          <div class="todo-list">
            <div v-for="task in todayTasks" :key="task.id" class="todo-item" @click="handleTaskClick(task)">
              <div class="todo-icon" :class="task.type">
                <el-icon v-if="task.type === 'follow'"><Phone /></el-icon>
                <el-icon v-else-if="task.type === 'meeting'"><Calendar /></el-icon>
                <el-icon v-else><Bell /></el-icon>
              </div>
              <div class="todo-content">
                <div class="todo-title">{{ task.title }}</div>
                <div class="todo-sub">{{ task.customer }} · {{ task.time }}</div>
              </div>
            </div>
            <el-empty v-if="!todayTasks.length" description="暂无待办事项" :image-size="60" />
          </div>
        </el-card>

        <!-- 快捷操作 -->
        <el-card shadow="never" class="section-card" style="margin-top: 16px;">
          <template #header>快捷操作</template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/sales/leads')">
              <el-icon><Plus /></el-icon> 新建线索
            </el-button>
            <el-button type="success" @click="$router.push('/sales/opportunities')">
              <el-icon><TrendCharts /></el-icon> 新建商机
            </el-button>
            <el-button @click="$router.push('/masterdata/customer-followups')">
              <el-icon><Edit /></el-icon> 添加跟进
            </el-button>
            <el-button @click="$router.push('/customers')">
              <el-icon><OfficeBuilding /></el-icon> 客户档案
            </el-button>
          </div>
        </el-card>

        <!-- 本月销售排名 -->
        <el-card shadow="never" class="section-card" style="margin-top: 16px;">
          <template #header>本月销售排名</template>
          <div class="ranking-list">
            <div v-for="(item, idx) in salesRanking" :key="item.name" class="ranking-item">
              <span class="rank" :class="{ top: idx < 3 }">{{ idx + 1 }}</span>
              <span class="name">{{ item.name }}</span>
              <span class="amount">¥{{ formatNumber(item.amount) }}</span>
            </div>
            <el-empty v-if="!salesRanking.length" description="暂无数据" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 底部：最新线索和跟进记录 -->
    <!-- 底部：最新线索和跟进记录 - 使用列表格式 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>最新线索</span>
              <el-button type="primary" link @click="$router.push('/sales/leads')">查看全部</el-button>
            </div>
          </template>
          <div class="data-list">
            <div v-for="lead in recentLeads" :key="lead.id" class="data-item" @click="$router.push('/sales/leads')">
              <div class="item-main">
                <span class="item-title">{{ lead.company_name }}</span>
                <el-tag :type="getLeadStatusType(lead.status)" size="small">{{ lead.status_display }}</el-tag>
              </div>
              <div class="item-sub">
                <span>{{ lead.contact_name }}</span>
                <span class="item-date">{{ formatDate(lead.created_at) }}</span>
              </div>
            </div>
            <el-empty v-if="!recentLeads.length" description="暂无线索" :image-size="60" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>最新跟进</span>
              <el-button type="primary" link @click="$router.push('/masterdata/customer-followups')">查看全部</el-button>
            </div>
          </template>
          <div class="data-list">
            <div v-for="follow in recentFollowups" :key="follow.id" class="data-item" @click="$router.push('/masterdata/customer-followups')">
              <div class="item-main">
                <span class="item-title">{{ follow.customer_name }}</span>
                <el-tag :type="getResultType(follow.result)" size="small">{{ follow.result_display }}</el-tag>
              </div>
              <div class="item-sub">
                <span>{{ follow.follow_type_display }} · {{ follow.subject }}</span>
                <span class="item-date">{{ follow.follow_date }}</span>
              </div>
            </div>
            <el-empty v-if="!recentFollowups.length" description="暂无跟进" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, TrendCharts, OfficeBuilding, Trophy, Plus, Phone, Calendar, Bell, Edit } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()

const stats = ref({})
const pipelineStages = ref([])
const recentOpportunities = ref([])
const recentLeads = ref([])
const recentFollowups = ref([])
const todayTasks = ref([])
const salesRanking = ref([])

const maxStageAmount = ref(1)

const formatNumber = (num) => {
  if (!num) return '0'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.substring(0, 10)
}

const getStageColor = (stage) => {
  const colors = {
    QUALIFICATION: '#409eff',
    NEEDS_ANALYSIS: '#67c23a',
    PROPOSAL: '#e6a23c',
    NEGOTIATION: '#f56c6c',
    CLOSED_WON: '#67c23a',
    CLOSED_LOST: '#909399'
  }
  return colors[stage] || '#409eff'
}

const getStageType = (stage) => {
  const types = {
    QUALIFICATION: 'info',
    NEEDS_ANALYSIS: 'primary',
    PROPOSAL: 'warning',
    NEGOTIATION: 'danger',
    CLOSED_WON: 'success',
    CLOSED_LOST: 'info'
  }
  return types[stage] || 'info'
}

const getStagePercent = (amount) => {
  if (!maxStageAmount.value) return 0
  return Math.round((amount / maxStageAmount.value) * 100)
}

const getLeadStatusType = (status) => {
  const types = { NEW: 'info', CONTACTED: 'primary', QUALIFIED: 'success', CONVERTED: 'success', DISQUALIFIED: 'danger' }
  return types[status] || 'info'
}

const getResultType = (result) => {
  const types = { POSITIVE: 'success', NEUTRAL: 'warning', NEGATIVE: 'danger', PENDING: 'info' }
  return types[result] || 'info'
}

const fetchDashboardData = async () => {
  try {
    // 获取统计数据
    const [statsData, stagesData, oppsData, leadsData, followupsData, rankingData] = await Promise.all([
      request.get('/sales/crm-dashboard/stats/').catch(() => ({})),
      request.get('/sales/analysis/stages/').catch(() => ({ stages: [] })),
      request.get('/sales/opportunities/', { params: { page_size: 5, ordering: '-updated_at' } }).catch(() => ({ results: [] })),
      request.get('/sales/leads/', { params: { page_size: 5, ordering: '-created_at' } }).catch(() => ({ results: [] })),
      request.get('/masterdata/customer-followups/', { params: { page_size: 5, ordering: '-follow_date' } }).catch(() => ({ results: [] })),
      request.get('/sales/analysis/ranking/', { params: { limit: 5 } }).catch(() => ({ ranking: [] }))
    ])

    stats.value = statsData || {}
    pipelineStages.value = stagesData.stages || []
    maxStageAmount.value = Math.max(...pipelineStages.value.map(s => s.amount || 0), 1)
    recentOpportunities.value = oppsData.results || oppsData || []
    recentLeads.value = leadsData.results || leadsData || []
    recentFollowups.value = followupsData.results || followupsData || []
    salesRanking.value = (rankingData.ranking || []).slice(0, 5)

    // 构建今日待办
    buildTodayTasks()
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  }
}

const buildTodayTasks = () => {
  const tasks = []
  // 从跟进记录中获取今日计划
  recentFollowups.value.forEach((f, idx) => {
    if (f.next_follow_date === new Date().toISOString().slice(0, 10)) {
      tasks.push({
        id: `follow-${idx}`,
        type: 'follow',
        title: f.next_follow_content || '跟进客户',
        customer: f.customer_name,
        time: f.next_follow_date
      })
    }
  })
  todayTasks.value = tasks
}

const handleTaskClick = (task) => {
  router.push('/masterdata/customer-followups')
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<style scoped>
.crm-dashboard {
  padding: 0;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-card .stat-icon {
  font-size: 40px;
  margin-right: 20px;
  opacity: 0.8;
}

.stat-leads .stat-icon { color: #409eff; }
.stat-opportunities .stat-icon { color: #67c23a; }
.stat-customers .stat-icon { color: #e6a23c; }
.stat-won .stat-icon { color: #f56c6c; }

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.stat-trend, .stat-amount, .stat-sub {
  font-size: 12px;
  margin-top: 8px;
}

.stat-trend.up { color: #67c23a; }
.stat-trend.down { color: #f56c6c; }
.stat-amount { color: #409eff; }
.stat-sub { color: #909399; }

.section-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pipeline-stages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pipeline-stage {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-left: 10px;
  border-left: 3px solid;
}

.stage-name {
  font-weight: 500;
}

.stage-amount {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
  margin: 8px 0;
}

.stage-bar {
  height: 6px;
  background: #e4e7ed;
  border-radius: 3px;
  overflow: hidden;
}

.stage-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.todo-list {
  max-height: 200px;
  overflow-y: auto;
}

.todo-item {
  display: flex;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;
}

.todo-item:hover {
  background: #f5f7fa;
}

.todo-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  font-size: 18px;
}

.todo-icon.follow { background: #e6f7ff; color: #409eff; }
.todo-icon.meeting { background: #f6ffed; color: #67c23a; }

.todo-content { flex: 1; }
.todo-title { font-weight: 500; }
.todo-sub { font-size: 12px; color: #909399; margin-top: 4px; }

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.quick-actions .el-button {
  flex: 1;
  min-width: 120px;
}

.ranking-list {
  max-height: 180px;
  overflow-y: auto;
}

.ranking-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed #f0f0f0;
}

.ranking-item .rank {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  margin-right: 10px;
}

.ranking-item .rank.top {
  background: #f56c6c;
  color: #fff;
}

.ranking-item .name {
  flex: 1;
}

.ranking-item .amount {
  font-weight: 500;
  color: #f56c6c;
}

/* 数据列表样式 */
.data-list {
  max-height: 220px;
  overflow-y: auto;
}

.data-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;
}

.data-item:hover {
  background: #f5f7fa;
}

.data-item:last-child {
  border-bottom: none;
}

.item-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.item-title {
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}

.item-sub {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

.item-sub span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}

.item-date {
  flex-shrink: 0;
}
</style>
