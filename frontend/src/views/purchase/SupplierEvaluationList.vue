<template>
  <div class="evaluation-container">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ statistics.total_evaluations || 0 }}</div>
          <div class="stat-label">评价总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card grade-a">
          <div class="stat-value">{{ getGradeCount('A') }}</div>
          <div class="stat-label">A级供应商</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card grade-b">
          <div class="stat-value">{{ getGradeCount('B') }}</div>
          <div class="stat-label">B级供应商</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ toFixedSafe(statistics.avg_scores?.avg_total, 1, '-') }}</div>
          <div class="stat-label">平均得分</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>供应商评价管理</span>
          <div class="header-actions">
            <el-button type="primary" v-permission="'purchase:supplier_evaluation:create'" @click="handleCreate">
              <el-icon><Plus /></el-icon> 新建评价
            </el-button>
            <el-button @click="showRanking = true">
              <el-icon><TrendCharts /></el-icon> 排名
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 筛选区 -->
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索评价编号/供应商" style="width: 220px" clearable @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchData" style="width: 120px">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="已提交" value="SUBMITTED" />
          <el-option label="已审批" value="APPROVED" />
          <el-option label="已驳回" value="REJECTED" />
        </el-select>
        <el-select v-model="queryParams.grade" placeholder="评价等级" clearable @change="fetchData" style="width: 120px">
          <el-option label="A级" value="A" />
          <el-option label="B级" value="B" />
          <el-option label="C级" value="C" />
          <el-option label="D级" value="D" />
          <el-option label="E级" value="E" />
        </el-select>
        <el-select v-model="queryParams.period_type" placeholder="评价周期" clearable @change="fetchData" style="width: 120px">
          <el-option label="月度" value="MONTHLY" />
          <el-option label="季度" value="QUARTERLY" />
          <el-option label="年度" value="YEARLY" />
          <el-option label="项目" value="PROJECT" />
          <el-option label="到货" value="DELIVERY" />
        </el-select>
      </div>

      <!-- 数据表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="evaluations" v-loading="loading" stripe style="width: 100%; margin-top: 16px" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="evaluation_no" label="评价编号" width="140" />
        <el-table-column label="供应商" min-width="180">
          <template #default="{ row }">
            <span>{{ row.supplier_detail?.name }}</span>
            <div class="text-muted">{{ row.supplier_detail?.code }}</div>
          </template>
        </el-table-column>
        <el-table-column label="评价周期" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.period_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="evaluation_date" label="评价日期" width="110" />
        <el-table-column label="总分" width="80" align="center">
          <template #default="{ row }">
            <span :class="getScoreClass(row.total_score)">{{ toFixedSafe(row.total_score, 1, '-') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="等级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getGradeType(row.grade)" size="small">{{ row.grade || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分项得分" width="200">
          <template #default="{ row }">
            <div class="score-breakdown">
              <span>质量: {{ toFixedSafe(row.quality_score, 0, '-') }}</span>
              <span>交期: {{ toFixedSafe(row.delivery_score, 0, '-') }}</span>
              <span>价格: {{ toFixedSafe(row.price_score, 0, '-') }}</span>
              <span>服务: {{ toFixedSafe(row.service_score, 0, '-') }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="evaluator_detail.username" label="评价人" width="100" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'DRAFT'" size="small" type="primary" @click="handleSubmit(row)">提交</el-button>
            <el-button v-if="row.status === 'SUBMITTED'" size="small" type="success" @click="handleApprove(row)">审批</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 供应商排名弹窗 -->
    <el-dialog v-model="showRanking" title="供应商排名" width="600px">
      <el-table :data="ranking" stripe>
        <el-table-column type="index" label="排名" width="60" />
        <el-table-column prop="supplier__name" label="供应商" />
        <el-table-column prop="supplier__code" label="编码" width="120" />
        <el-table-column label="平均分" width="100">
          <template #default="{ row }">
            <span :class="getScoreClass(row.avg_score)">{{ toFixedSafe(row.avg_score, 1, '-') }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="evaluation_count" label="评价次数" width="100" />
      </el-table>
    </el-dialog>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier">
              <el-select v-model="form.supplier" placeholder="选择供应商" filterable style="width: 100%">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="评价模板" prop="template">
              <el-select v-model="form.template" placeholder="选择模板" @change="loadTemplate" style="width: 100%">
                <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="评价周期" prop="period_type">
              <el-select v-model="form.period_type" style="width: 100%">
                <el-option label="月度" value="MONTHLY" />
                <el-option label="季度" value="QUARTERLY" />
                <el-option label="年度" value="YEARLY" />
                <el-option label="项目" value="PROJECT" />
                <el-option label="到货" value="DELIVERY" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="开始日期" prop="period_start">
              <el-date-picker v-model="form.period_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="结束日期" prop="period_end">
              <el-date-picker v-model="form.period_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="评价日期" prop="evaluation_date">
          <el-date-picker v-model="form.evaluation_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>

        <!-- 评分明细 -->
        <el-divider>评分明细</el-divider>
        <el-table :data="criteriaList" stripe size="small">
          <el-table-column prop="name" label="指标" />
          <el-table-column prop="category_display" label="类别" width="80" />
          <el-table-column prop="weight" label="权重" width="60" />
          <el-table-column label="评分" width="150">
            <template #default="{ row, $index }">
              <el-input-number v-model="scoreItems[$index].score" :min="0" :max="row.max_score" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="说明" min-width="150">
            <template #default="{ $index }">
              <el-input v-model="scoreItems[$index].comments" size="small" placeholder="评价说明" />
            </template>
          </el-table-column>
        </el-table>

        <el-form-item label="综合评价" prop="comments" style="margin-top: 16px">
          <el-input v-model="form.comments" type="textarea" rows="3" />
        </el-form-item>
        <el-form-item label="改进建议" prop="improvement_suggestions">
          <el-input v-model="form.improvement_suggestions" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 评价详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="评价详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="供应商">{{ viewDetail.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="评价周期">{{ viewDetail.period_type_display || viewDetail.period_type }}</el-descriptions-item>
        <el-descriptions-item label="评价日期">{{ viewDetail.evaluation_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag>{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="综合得分" :span="2">
          <span style="font-size: 24px; font-weight: bold; color: #409EFF">{{ viewDetail.total_score || 0 }}</span> 分
        </el-descriptions-item>
        <el-descriptions-item label="评级">
          <el-tag :type="viewDetail.grade === 'A' ? 'success' : viewDetail.grade === 'D' ? 'danger' : ''">{{ viewDetail.grade || '-' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="评价周期">{{ viewDetail.period_start }} ~ {{ viewDetail.period_end }}</el-descriptions-item>
        <el-descriptions-item label="评审意见" :span="2">{{ viewDetail.comments || '-' }}</el-descriptions-item>
        <el-descriptions-item label="改进建议" :span="2">{{ viewDetail.improvement_suggestions || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template v-if="viewDetail.scores && viewDetail.scores.length">
        <h4 style="margin: 16px 0 8px">评分明细</h4>
        <el-table :data="viewDetail.scores" stripe size="small">
          <el-table-column prop="criteria_name" label="评价项" />
          <el-table-column prop="score" label="得分" width="80" align="center" />
          <el-table-column prop="weight" label="权重" width="80" align="center" />
          <el-table-column prop="weighted_score" label="加权分" width="80" align="center" />
          <el-table-column prop="comments" label="备注" />
        </el-table>
      </template>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, TrendCharts } from '@element-plus/icons-vue'
import { toFixedSafe } from '@/utils/number'
import {
  getEvaluationList, getEvaluation, createEvaluation, submitEvaluation,
  approveEvaluation, getEvaluationStatistics, getSupplierRanking,
  getEvaluationTemplateList
} from '@/api/purchase/evaluation'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/purchase/evaluations/', { onSuccess: () => fetchData() })

const loading = ref(false)
const evaluations = ref<any[]>([])
const total = ref(0)
const statistics = ref<Record<string, any>>({})
const ranking = ref<any[]>([])
const showRanking = ref(false)
const templates = ref<any[]>([])
const suppliers = ref<any[]>([])
const criteriaList = ref<any[]>([])
const scoreItems = ref<any[]>([])

const dialogVisible = ref(false)
const dialogTitle = ref('新建评价')

const queryParams = reactive({
  search: '',
  status: '',
  grade: '',
  period_type: '',
  page: 1,
  page_size: 20
})

const form = reactive({
  supplier: null,
  template: null,
  period_type: 'QUARTERLY',
  evaluation_date: '',
  period_start: '',
  period_end: '',
  comments: '',
  improvement_suggestions: ''
})

const rules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  template: [{ required: true, message: '请选择评价模板', trigger: 'change' }],
  period_type: [{ required: true, message: '请选择评价周期', trigger: 'change' }],
  evaluation_date: [{ required: true, message: '请选择评价日期', trigger: 'change' }],
  period_start: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  period_end: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

const getGradeCount = (grade) => {
  const gradeData = statistics.value.by_grade?.find(g => g.grade === grade)
  return gradeData?.count || 0
}

const getGradeType = (grade) => {
  const map = { A: 'success', B: 'primary', C: 'warning', D: 'danger', E: 'info' }
  return map[grade] || 'info'
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', SUBMITTED: 'warning', APPROVED: 'success', REJECTED: 'danger' }
  return map[status] || ''
}

const getScoreClass = (score) => {
  if (score >= 90) return 'score-excellent'
  if (score >= 80) return 'score-good'
  if (score >= 70) return 'score-fair'
  if (score >= 60) return 'score-poor'
  return 'score-bad'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getEvaluationList(queryParams)
    evaluations.value = res.results || res || []
    total.value = res.count || evaluations.value.length
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const fetchStatistics = async () => {
  try {
    const res = await getEvaluationStatistics()
    statistics.value = res || {}
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const fetchRanking = async () => {
  try {
    const res = await getSupplierRanking()
    ranking.value = res || []
  } catch (error) {
    console.error('获取排名失败', error)
  }
}

const fetchTemplates = async () => {
  try {
    const res = await getEvaluationTemplateList({ is_active: true })
    templates.value = res.results || res || []
  } catch (error) {
    console.error('获取模板失败', error)
  }
}

const loadTemplate = async (templateId) => {
  const template = templates.value.find(t => t.id === templateId)
  if (template && template.criteria) {
    criteriaList.value = template.criteria
    scoreItems.value = template.criteria.map(c => ({
      criteria: c.id,
      score: 0,
      comments: ''
    }))
  }
}

const handleCreate = () => {
  dialogTitle.value = '新建评价'
  Object.assign(form, {
    supplier: null,
    template: null,
    period_type: 'QUARTERLY',
    evaluation_date: new Date().toISOString().split('T')[0],
    period_start: '',
    period_end: '',
    comments: '',
    improvement_suggestions: ''
  })
  criteriaList.value = []
  scoreItems.value = []
  dialogVisible.value = true
}

const viewDialogVisible = ref(false)
const viewDetail = ref<Record<string, any>>({})

const handleView = async (row) => {
  try {
    const res = await getEvaluation(row.id)
    viewDetail.value = res
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交此评价吗？', '确认')
    await submitEvaluation(row.id)
    ElMessage.success('提交成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('提交失败')
  }
}

const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要审批通过此评价吗？', '确认')
    await approveEvaluation(row.id, { comments: '' })
    ElMessage.success('审批成功')
    fetchData()
    fetchStatistics()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('审批失败')
  }
}

const handleSave = async () => {
  try {
    const data = {
      ...form,
      score_items: scoreItems.value.filter(s => s.score > 0)
    }
    await createEvaluation(data)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchData()
    fetchStatistics()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

onMounted(() => {
  fetchData()
  fetchStatistics()
  fetchRanking()
  fetchTemplates()
})
</script>

<style scoped>
.evaluation-container {
  padding: 20px;
}
.stat-cards {
  margin-bottom: 20px;
}
.stat-card {
  text-align: center;
  padding: 10px;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
.stat-card.grade-a .stat-value { color: #67c23a; }
.stat-card.grade-b .stat-value { color: #409eff; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.filter-area {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.text-muted {
  font-size: 12px;
  color: #909399;
}
.score-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #606266;
}
.score-excellent { color: #67c23a; font-weight: bold; }
.score-good { color: #409eff; font-weight: bold; }
.score-fair { color: #e6a23c; font-weight: bold; }
.score-poor { color: #f56c6c; font-weight: bold; }
.score-bad { color: #909399; }
</style>
