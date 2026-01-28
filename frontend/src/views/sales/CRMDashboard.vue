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
    <el-row :gutter="16" class="content-row">
      <!-- 左侧 -->
      <el-col :span="16">
        <!-- 商机阶段分布 -->
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

        <!-- 最新线索 -->
        <el-card shadow="never" class="section-card" style="margin-top: 16px;">
          <template #header>
            <div class="card-header">
              <span>最新线索</span>
              <el-button type="primary" link @click="$router.push('/sales/leads')">查看全部</el-button>
            </div>
          </template>
          <div class="simple-list">
            <div v-for="lead in recentLeads" :key="lead.id" class="simple-item">
              <div class="simple-title">{{ lead.company_name }}</div>
              <div class="simple-info">
                <span>{{ lead.contact_name }}</span>
                <el-tag :type="getLeadStatusType(lead.status)" size="small">{{ lead.status_display }}</el-tag>
              </div>
            </div>
            <el-empty v-if="!recentLeads.length" description="暂无线索" :image-size="50" />
          </div>
        </el-card>
      </el-col>

      <!-- 右侧 -->
      <el-col :span="8">
        <!-- 快捷操作 -->
        <el-card shadow="never" class="section-card">
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
            <el-button @click="$router.push('/masterdata/customers')">
              <el-icon><OfficeBuilding /></el-icon> 客户档案
            </el-button>
          </div>
        </el-card>

        <!-- 最新跟进 -->
        <el-card shadow="never" class="section-card" style="margin-top: 16px;">
          <template #header>
            <div class="card-header">
              <span>最新跟进</span>
              <el-button type="primary" link @click="$router.push('/masterdata/customer-followups')">查看全部</el-button>
            </div>
          </template>
          <div class="simple-list">
            <div v-for="follow in recentFollowups" :key="follow.id" class="simple-item">
              <div class="simple-title">{{ follow.customer_name }}</div>
              <div class="simple-info">
                <span>{{ follow.follow_type_display }}</span>
                <el-tag :type="getResultType(follow.result)" size="small">{{ follow.result_display }}</el-tag>
              </div>
            </div>
            <el-empty v-if="!recentFollowups.length" description="暂无跟进" :image-size="50" />
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
            <el-empty v-if="!salesRanking.length" description="暂无数据" :image-size="50" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, TrendCharts, OfficeBuilding, Trophy, Plus, Edit } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()

const stats = ref({})
const pipelineStages = ref([])
const recentLeads = ref([])
const recentFollowups = ref([])
const salesRanking = ref([])

const maxStageAmount = ref(1)

const formatNumber = (num) => {
  if (!num) return '0'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
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
    const [statsData, stagesData, leadsData, followupsData, rankingData] = await Promise.all([
      request.get('/sales/crm-dashboard/stats/').catch(() => ({})),
      request.get('/sales/analysis/stages/').catch(() => ({ stages: [] })),
      request.get('/sales/leads/', { params: { page_size: 5, ordering: '-created_at' } }).catch(() => ({ results: [] })),
      request.get('/masterdata/customer-followups/', { params: { page_size: 5, ordering: '-follow_date' } }).catch(() => ({ results: [] })),
      request.get('/sales/analysis/ranking/', { params: { limit: 5 } }).catch(() => ({ ranking: [] }))
    ])

    stats.value = statsData || {}
    pipelineStages.value = stagesData.stages || []
    maxStageAmount.value = Math.max(...pipelineStages.value.map(s => s.amount || 0), 1)
    recentLeads.value = leadsData.results || leadsData || []
    recentFollowups.value = followupsData.results || followupsData || []
    salesRanking.value = (rankingData.ranking || []).slice(0, 5)
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  }
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
  padding: 16px;
}

.stat-card .stat-icon {
  font-size: 36px;
  margin-right: 16px;
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
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}

.stat-trend, .stat-amount, .stat-sub {
  font-size: 12px;
  margin-top: 4px;
}

.stat-trend.up { color: #67c23a; }
.stat-trend.down { color: #f56c6c; }
.stat-amount { color: #409eff; }
.stat-sub { color: #909399; }

.content-row {
  margin-bottom: 16px;
}

.section-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pipeline-stages {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pipeline-stage {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-left: 8px;
  border-left: 3px solid;
}

.stage-name {
  font-weight: 500;
  font-size: 13px;
}

.stage-amount {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin: 4px 0;
}

.stage-bar {
  height: 4px;
  background: #e4e7ed;
  border-radius: 2px;
  overflow: hidden;
}

.stage-bar-fill {
  height: 100%;
  border-radius: 2px;
}

/* 简化的列表样式 */
.simple-list {
  max-height: 200px;
  overflow-y: auto;
}

.simple-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.simple-item:last-child {
  border-bottom: none;
}

.simple-title {
  font-weight: 500;
  font-size: 13px;
  color: #303133;
  margin-bottom: 4px;
}

.simple-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-actions .el-button {
  flex: 1;
  min-width: 100px;
}

.ranking-list {
  max-height: 150px;
  overflow-y: auto;
}

.ranking-item {
  display: flex;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed #f0f0f0;
}

.ranking-item:last-child {
  border-bottom: none;
}

.ranking-item .rank {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  margin-right: 8px;
}

.ranking-item .rank.top {
  background: #f56c6c;
  color: #fff;
}

.ranking-item .name {
  flex: 1;
  font-size: 13px;
}

.ranking-item .amount {
  font-weight: 500;
  color: #f56c6c;
  font-size: 13px;
}
</style>
