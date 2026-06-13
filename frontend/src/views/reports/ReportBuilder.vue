<template>
  <div class="report-builder">
    <el-row :gutter="16">
      <!-- 报表模板列表 -->
      <el-col :span="7">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>报表模板</span>
              <el-button type="primary" size="small" @click="showTemplateDialog = true"><el-icon><Plus /></el-icon>新建</el-button>
            </div>
          </template>
          <el-input v-model="searchTemplate" placeholder="搜索模板" clearable style="margin-bottom: 12px" />
          <div class="template-list">
            <div v-for="tpl in filteredTemplates" :key="tpl.id" class="template-item"
              :class="{ active: selectedTemplate?.id === tpl.id }" @click="selectTemplate(tpl)">
              <div class="template-name">{{ tpl.name }}</div>
              <div class="template-meta">
                <el-tag size="small">{{ categoryLabel(tpl.category) }}</el-tag>
                <el-icon v-if="tpl.is_favorite" style="color:#e6a23c"><StarFilled /></el-icon>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 我的收藏 -->
        <el-card style="margin-top: 16px">
          <template #header>收藏的报表</template>
          <div class="template-list">
            <div v-for="fav in favorites" :key="fav.id" class="template-item" @click="selectTemplate(fav)">
              <div class="template-name">{{ fav.name }}</div>
            </div>
            <el-empty v-if="!favorites.length" description="暂无收藏" :image-size="60" />
          </div>
        </el-card>
      </el-col>

      <!-- 报表配置与结果 -->
      <el-col :span="17">
        <el-card v-if="selectedTemplate">
          <template #header>
            <div class="card-header">
              <span>{{ selectedTemplate.name }}</span>
              <div>
                <el-button @click="toggleFavorite" :type="selectedTemplate.is_favorite ? 'warning' : ''">
                  <el-icon><Star /></el-icon>{{ selectedTemplate.is_favorite ? '取消收藏' : '收藏' }}
                </el-button>
                <el-button type="primary" @click="executeReport" :loading="executing">
                  <el-icon><VideoPlay /></el-icon>执行
                </el-button>
                <el-button @click="exportReport" :disabled="!reportData.length">
                  <el-icon><Download /></el-icon>导出
                </el-button>
              </div>
            </div>
          </template>

          <!-- 过滤条件 -->
          <div v-if="selectedTemplate.config?.filters?.length" class="filter-section">
            <el-form :inline="true" size="small">
              <el-form-item v-for="filter in selectedTemplate.config.filters" :key="filter.field" :label="filter.label || filter.field">
                <el-input v-if="!filter.type || filter.type === 'text'" v-model="filterValues[filter.field]" :placeholder="filter.label" clearable style="width: 180px" />
                <el-date-picker v-else-if="filter.type === 'daterange'" v-model="filterValues[filter.field]" type="daterange"
                  range-separator="-" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 240px" />
                <el-select v-else-if="filter.type === 'select'" v-model="filterValues[filter.field]" clearable style="width: 180px">
                  <el-option v-for="opt in (filter.options || [])" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>

          <!-- 结果表格 -->
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="reportData" v-loading="executing" stripe max-height="500" style="margin-top: 12px" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column v-for="col in reportColumns" :key="col.prop" :prop="col.prop" :label="col.label" :min-width="col.width || 120" />
          </el-table>

          <!-- 图表 -->
          <div v-if="selectedTemplate.config?.chart_type" ref="chartRef" style="height: 350px; margin-top: 16px;"></div>
        </el-card>

        <el-card v-else>
          <el-empty description="请从左侧选择一个报表模板" />
        </el-card>

        <!-- 执行历史 -->
        <el-card style="margin-top: 16px">
          <template #header>执行历史</template>
          <el-table :data="executions" size="small" stripe max-height="250">
            <el-table-column prop="template_name" label="模板" min-width="150" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : (row.status === 'failed' ? 'danger' : 'warning')" size="small">
                  {{ { pending: '等待', running: '运行', completed: '完成', failed: '失败' }[row.status] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="row_count" label="行数" width="80" align="center" />
            <el-table-column prop="execution_time" label="耗时(秒)" width="100" align="center" />
            <el-table-column prop="created_at" label="执行时间" width="160" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新建模板对话框 -->
    <el-dialog v-model="showTemplateDialog" title="新建报表模板" width="700px">
      <el-form :model="templateForm" :rules="templateRules" ref="templateFormRef" label-width="100px">
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="templateForm.name" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="templateForm.category" style="width:100%">
                <el-option label="销售" value="sales" /><el-option label="采购" value="purchase" />
                <el-option label="库存" value="inventory" /><el-option label="生产" value="production" />
                <el-option label="财务" value="finance" /><el-option label="项目" value="project" />
                <el-option label="质量" value="quality" /><el-option label="设备" value="equipment" />
                <el-option label="综合" value="comprehensive" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据源" prop="data_source">
              <el-select v-model="templateForm.data_source" style="width:100%">
                <el-option label="销售订单" value="sales_order" /><el-option label="采购订单" value="purchase_order" />
                <el-option label="库存" value="stock" /><el-option label="生产工单" value="production_order" />
                <el-option label="项目" value="project" /><el-option label="质量检验" value="inspection" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input type="textarea" v-model="templateForm.description" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTemplateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTemplate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Star, StarFilled, VideoPlay, Download } from '@element-plus/icons-vue'
import {
getReportTemplates, createReportTemplate, executeReportTemplate,
  favoriteReportTemplate, getMyFavoriteReports, getReportExecutions
} from '@/api/reports'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/')


const templates = ref<any[]>([])
const favorites = ref<any[]>([])
const executions = ref<any[]>([])
const selectedTemplate = ref(null)
const reportData = ref<any[]>([])
const reportColumns = ref<any[]>([])
const executing = ref(false)
const showTemplateDialog = ref(false)
const templateFormRef = ref(null)
const searchTemplate = ref('')
const chartRef = ref(null)
const filterValues = reactive<Record<string, any>>({})

const templateForm = reactive({ name: '', category: '', data_source: '', description: '' })

const templateRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  data_source: [{ required: true, message: '请选择数据源', trigger: 'change' }]
}

const categoryLabel = (c) => ({ sales: '销售', purchase: '采购', inventory: '库存', production: '生产', finance: '财务', project: '项目', quality: '质量', equipment: '设备', comprehensive: '综合' }[c] || c)

const filteredTemplates = computed(() => {
  if (!searchTemplate.value) return templates.value
  const kw = searchTemplate.value.toLowerCase()
  return templates.value.filter(t => t.name.toLowerCase().includes(kw))
})

const loadTemplates = async () => {
  const res = await getReportTemplates({ page_size: 100 })
  templates.value = res.results || res.results || []
}

const loadFavorites = async () => {
  const res = await getMyFavoriteReports()
  favorites.value = res || []
}

const loadExecutions = async () => {
  const res = await getReportExecutions({ page_size: 20 })
  executions.value = res.results || res.results || []
}

const selectTemplate = (tpl) => {
  selectedTemplate.value = tpl
  reportData.value = []
  reportColumns.value = []
  Object.keys(filterValues).forEach(k => delete filterValues[k])
}

const executeReport = async () => {
  executing.value = true
  try {
    const res = await executeReportTemplate(selectedTemplate.value.id, { parameters: filterValues })
    if (res.status === 'failed') {
      ElMessage.error(res.error_message || '报表执行失败')
      reportData.value = []
      reportColumns.value = []
    } else {
      reportData.value = res.result_data?.rows || []
      if (reportData.value.length) {
        reportColumns.value = Object.keys(reportData.value[0]).map(k => ({ prop: k, label: k }))
      } else {
        reportColumns.value = []
        ElMessage.info('报表执行成功，但无数据')
      }
    }
    loadExecutions()
  } finally { executing.value = false }
}

const toggleFavorite = async () => {
  await favoriteReportTemplate(selectedTemplate.value.id)
  selectedTemplate.value.is_favorite = !selectedTemplate.value.is_favorite
  ElMessage.success(selectedTemplate.value.is_favorite ? '已收藏' : '已取消')
  loadFavorites()
}

const exportReport = () => {
  if (!reportData.value.length) return
  const headers = reportColumns.value.map(c => c.label).join(',')
  const rows = reportData.value.map(r => reportColumns.value.map(c => r[c.prop] ?? '').join(','))
  const csv = [headers, ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = selectedTemplate.value.name + '_' + new Date().toISOString().slice(0, 10) + '.csv'
  link.click()
}

const createTemplate = async () => {
  await templateFormRef.value.validate()
  await createReportTemplate(templateForm)
  ElMessage.success('创建成功')
  showTemplateDialog.value = false
  loadTemplates()
}

onMounted(() => { loadTemplates(); loadFavorites(); loadExecutions() })
</script>

<style scoped>
.report-builder { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-section { padding: 12px; background: #f5f7fa; border-radius: 4px; }
.template-list { max-height: 400px; overflow-y: auto; }
.template-item { padding: 10px 12px; cursor: pointer; border-radius: 4px; margin-bottom: 4px; transition: background 0.2s; }
.template-item:hover { background: #ecf5ff; }
.template-item.active { background: #409eff; color: white; }
.template-item.active .template-meta .el-tag { color: white; }
.template-name { font-weight: 500; margin-bottom: 4px; }
.template-meta { display: flex; justify-content: space-between; align-items: center; }
</style>
