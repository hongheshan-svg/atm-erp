<template>
  <div class="inspection-container">
    <div class="page-header">
      <h2>设备点检</h2>
      <el-button type="primary" v-permission="'projects:project:create'" @click="handleCreateInspection">
        <el-icon><Plus /></el-icon> 新建点检
      </el-button>
    </div>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="点检记录" name="records">
        <!-- 统计卡片 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="6">
            <el-card shadow="never" class="stat-card">
              <div class="stat-value">{{ todayStats.total || 0 }}</div>
              <div class="stat-label">今日点检</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-success">
              <div class="stat-value">{{ todayStats.completed || 0 }}</div>
              <div class="stat-label">已完成</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-warning">
              <div class="stat-value">{{ todayStats.pending || 0 }}</div>
              <div class="stat-label">待点检</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-danger">
              <div class="stat-value">{{ todayStats.abnormal || 0 }}</div>
              <div class="stat-label">有异常</div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 筛选 -->
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" :model="queryParams">
            <el-form-item label="设备">
              <el-select v-model="queryParams.equipment" placeholder="全部" clearable filterable style="width: 160px">
                <el-option v-for="e in equipments" :key="e.id" :label="e.name" :value="e.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="queryParams.status" placeholder="全部" clearable>
                <el-option label="待点检" value="PENDING" />
                <el-option label="点检中" value="IN_PROGRESS" />
                <el-option label="已完成" value="COMPLETED" />
                <el-option label="有异常" value="ABNORMAL" />
              </el-select>
            </el-form-item>
            <el-form-item label="日期">
              <el-date-picker v-model="queryParams.inspection_date" type="date" placeholder="选择日期" 
                value-format="YYYY-MM-DD" style="width: 150px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="fetchData">查询</el-button>
              <el-button @click="resetQuery">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        
        <!-- 点检记录列表 -->
        <el-card shadow="never">
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="tableData" v-loading="loading" border stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="record_no" label="记录编号" width="160" />
            <el-table-column prop="equipment_name" label="设备" width="140" show-overflow-tooltip />
            <el-table-column prop="template_name" label="点检模板" width="140" show-overflow-tooltip />
            <el-table-column prop="inspection_date" label="点检日期" width="110" />
            <el-table-column prop="shift" label="班次" width="80">
              <template #default="{ row }">
                {{ row.shift === 'DAY' ? '白班' : row.shift === 'NIGHT' ? '夜班' : '全天' }}
              </template>
            </el-table-column>
            <el-table-column prop="inspector_name" label="点检人" width="90" />
            <el-table-column label="点检进度" width="120">
              <template #default="{ row }">
                {{ row.checked_items }}/{{ row.total_items }}
                <el-progress :percentage="row.total_items ? Math.round(row.checked_items / row.total_items * 100) : 0" 
                  :stroke-width="6" style="margin-top: 4px" />
              </template>
            </el-table-column>
            <el-table-column label="正常/异常" width="100" align="center">
              <template #default="{ row }">
                <span class="text-success">{{ row.normal_items }}</span> / 
                <span class="text-danger">{{ row.abnormal_items }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getStatusTag(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleView(row)">查看</el-button>
                <el-button type="success" link size="small" @click="handleDoInspection(row)" 
                  v-if="['PENDING', 'IN_PROGRESS'].includes(row.status)">点检</el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            class="pagination"
            v-model:current-page="queryParams.page"
            v-model:page-size="queryParams.page_size"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            @size-change="fetchData"
            @current-change="fetchData"
          />
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="点检模板" name="templates">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>点检模板列表</span>
              <el-button type="primary" size="small" v-permission="'projects:project:create'" @click="handleAddTemplate">新增模板</el-button>
            </div>
          </template>
          <el-table :data="templates" border stripe>
            <el-table-column prop="code" label="模板编码" width="120" />
            <el-table-column prop="name" label="模板名称" min-width="150" />
            <el-table-column prop="template_type_display" label="类型" width="100" />
            <el-table-column prop="equipment_type" label="适用设备" width="120" />
            <el-table-column prop="item_count" label="点检项数" width="90" align="center" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewTemplate(row)">查看</el-button>
                <el-button type="primary" link size="small" @click="handleCopyTemplate(row)">复制</el-button>
                <el-button type="primary" link size="small" v-permission="'projects:project:edit'" @click="handleEditTemplate(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="异常处理" name="abnormal">
        <el-card shadow="never">
          <template #header>
            <span>未处理的异常项</span>
          </template>
          <el-table :data="unhandledAbnormal" border stripe>
            <el-table-column label="点检记录" width="160">
              <template #default="{ row }">
                {{ row.record?.record_no }}
              </template>
            </el-table-column>
            <el-table-column label="点检项" prop="item_name" width="150" />
            <el-table-column label="检查时间" width="170">
              <template #default="{ row }">
                {{ formatDateTime(row.check_time) }}
              </template>
            </el-table-column>
            <el-table-column label="结果值" prop="result_value" width="100" />
            <el-table-column label="异常描述" prop="abnormal_desc" min-width="200" show-overflow-tooltip />
            <el-table-column label="异常等级" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getAbnormalLevelTag(row.abnormal_level)">
                  {{ getAbnormalLevelText(row.abnormal_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleHandleAbnormal(row)">处理</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
    
    <!-- 新建点检对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建点检记录" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="设备">
          <el-select v-model="createForm.equipment_id" placeholder="选择设备" filterable style="width: 100%">
            <el-option v-for="e in equipments" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="点检模板">
          <el-select v-model="createForm.template_id" placeholder="选择模板" filterable style="width: 100%">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="点检日期">
          <el-date-picker v-model="createForm.inspection_date" type="date" style="width: 100%" 
            value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCreate" :loading="createLoading">创建</el-button>
      </template>
    </el-dialog>
    
    <!-- 处理异常对话框 -->
    <el-dialog v-model="handleDialogVisible" title="处理异常" width="500px">
      <el-form :model="handleForm" label-width="80px">
        <el-form-item label="异常项">
          <span>{{ currentAbnormal?.item_name }}</span>
        </el-form-item>
        <el-form-item label="异常描述">
          <span>{{ currentAbnormal?.abnormal_desc }}</span>
        </el-form-item>
        <el-form-item label="处理说明">
          <el-input v-model="handleForm.notes" type="textarea" :rows="4" placeholder="请输入处理说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmHandle" :loading="handleLoading">确认处理</el-button>
      </template>
    </el-dialog>

    <!-- 模板编辑 -->
    <el-dialog v-model="templateDialogVisible" :title="templateIsEdit ? '编辑模板' : '添加模板'" width="600px">
      <el-form label-width="100px">
        <el-form-item label="模板编码">
          <el-input v-model="templateForm.code" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="模板名称">
          <el-input v-model="templateForm.name" />
        </el-form-item>
        <el-form-item label="设备类型">
          <el-input v-model="templateForm.equipment_type" />
        </el-form-item>
        <el-form-item label="点检频率">
          <el-select v-model="templateForm.frequency" style="width: 100%">
            <el-option label="每日" value="DAILY" />
            <el-option label="每周" value="WEEKLY" />
            <el-option label="每月" value="MONTHLY" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="templateForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="templateSaving" @click="handleTemplateSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模板详情 -->
    <el-dialog v-model="templateDetailVisible" title="模板详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="编码">{{ templateDetail.code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ templateDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">{{ templateDetail.equipment_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="频率">{{ templateDetail.frequency_display || templateDetail.frequency }}</el-descriptions-item>
        <el-descriptions-item label="检查项数">{{ templateDetail.items_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ templateDetail.is_active ? '启用' : '停用' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ templateDetail.description || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="templateDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 点检详情 -->
    <el-dialog v-model="inspectionViewVisible" title="点检详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="设备">{{ inspectionDetail.equipment_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模板">{{ inspectionDetail.template_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="计划日期">{{ inspectionDetail.planned_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际日期">{{ inspectionDetail.actual_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ inspectionDetail.status_display || inspectionDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="执行人">{{ inspectionDetail.inspector_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="结果" :span="2">{{ inspectionDetail.result || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ inspectionDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="inspectionViewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 执行点检 -->
    <el-dialog v-model="doInspectionVisible" title="执行点检" width="600px">
      <el-alert title="请逐项检查并记录结果" type="info" :closable="false" style="margin-bottom: 16px" />
      <el-form label-width="100px">
        <el-form-item label="设备">{{ doInspectionRow?.equipment_name }}</el-form-item>
        <el-form-item label="检查结果">
          <el-radio-group v-model="inspectionResults.overall">
            <el-radio label="PASS">合格</el-radio>
            <el-radio label="FAIL">不合格</el-radio>
            <el-radio label="NEED_REPAIR">需维修</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="inspectionResults.remarks" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="doInspectionVisible = false">取消</el-button>
        <el-button type="primary" :loading="doInspectionSaving" @click="submitInspection">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
getEquipmentList,
  getInspectionRecordList, getInspectionRecord, getInspectionStatistics,
  createInspectionFromTemplate, completeInspectionRecord,
  getInspectionTemplateList, getInspectionTemplate,
  createInspectionTemplate, updateInspectionTemplate, copyInspectionTemplate,
  getUnhandledAbnormal, handleInspectionAbnormal
} from '@/api/equipment'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/inspection-records/')


const activeTab = ref('records')
const loading = ref(false)
const createLoading = ref(false)
const handleLoading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const templates = ref<any[]>([])
const templateDialogVisible = ref(false)
const templateIsEdit = ref(false)
const templateSaving = ref(false)
const templateForm = reactive({ id: null, code: '', name: '', equipment_type: '', frequency: 'DAILY', items_count: 0, description: '' })
const templateDetail = ref<Record<string, any>>({})
const inspectionViewVisible = ref(false)
const inspectionDetail = ref<Record<string, any>>({})
const doInspectionVisible = ref(false)
const doInspectionRow = ref(null)
const inspectionResults = reactive<any[]>([])
const doInspectionSaving = ref(false)
const templateDetailVisible = ref(false)
const equipments = ref<any[]>([])
const unhandledAbnormal = ref<any[]>([])
const todayStats = ref<Record<string, any>>({})

const createDialogVisible = ref(false)
const handleDialogVisible = ref(false)
const currentAbnormal = ref(null)

const queryParams = reactive({
  page: 1,
  page_size: 10,
  equipment: null,
  status: null,
  inspection_date: null
})

const createForm = reactive({
  equipment_id: null,
  template_id: null,
  inspection_date: new Date().toISOString().split('T')[0]
})

const handleForm = reactive({
  notes: ''
})

const fetchData = async () => {
  loading.value = true
  try {
    const data = await getInspectionRecordList(queryParams)
    tableData.value = data.results || data
    total.value = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchTemplates = async () => {
  try {
    const data = await getInspectionTemplateList({ page_size: 100 })
    templates.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchEquipments = async () => {
  try {
    const data = await getEquipmentList({ page_size: 500 })
    equipments.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchStats = async () => {
  try {
    const data = await getInspectionStatistics()
    todayStats.value = data.today || {}
  } catch (e) {
    console.error(e)
  }
}

const fetchUnhandledAbnormal = async () => {
  try {
    const data = await getUnhandledAbnormal()
    unhandledAbnormal.value = data
  } catch (e) {
    console.error(e)
  }
}

const resetQuery = () => {
  queryParams.equipment = null
  queryParams.status = null
  queryParams.inspection_date = null
  queryParams.page = 1
  fetchData()
}

const handleCreateInspection = () => {
  createForm.equipment_id = null
  createForm.template_id = null
  createForm.inspection_date = new Date().toISOString().split('T')[0]
  createDialogVisible.value = true
}

const confirmCreate = async () => {
  if (!createForm.equipment_id || !createForm.template_id) {
    ElMessage.warning('请选择设备和模板')
    return
  }
  
  createLoading.value = true
  try {
    await createInspectionFromTemplate(createForm)
    ElMessage.success('点检记录已创建')
    createDialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    createLoading.value = false
  }
}

const handleView = async (row) => {
  try {
    const res = await getInspectionRecord(row.id)
    inspectionDetail.value = res
  } catch (error) {
    console.error(error)
    inspectionDetail.value = row
  }
  inspectionViewVisible.value = true
}

const handleDoInspection = async (row) => {
  doInspectionRow.value = row
  doInspectionVisible.value = true
}

const submitInspection = async () => {
  doInspectionSaving.value = true
  try {
    await completeInspectionRecord(doInspectionRow.value.id, { results: inspectionResults })
    ElMessage.success('点检完成')
    doInspectionVisible.value = false
    fetchData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
    else ElMessage.error('提交失败')
  } finally {
    doInspectionSaving.value = false
  }
}

const handleAddTemplate = () => {
  templateIsEdit.value = false
  Object.assign(templateForm, { id: null, code: '', name: '', equipment_type: '', frequency: 'DAILY', description: '' })
  templateDialogVisible.value = true
}

const handleViewTemplate = async (row) => {
  try {
    const res = await getInspectionTemplate(row.id)
    templateDetail.value = res
  } catch (error) {
    console.error(error)
    templateDetail.value = row
  }
  templateDetailVisible.value = true
}

const handleEditTemplate = (row) => {
  templateIsEdit.value = true
  Object.assign(templateForm, { id: row.id, code: row.code, name: row.name, equipment_type: row.equipment_type, frequency: row.frequency, description: row.description })
  templateDialogVisible.value = true
}

const handleTemplateSave = async () => {
  templateSaving.value = true
  try {
    if (templateIsEdit.value) {
      await updateInspectionTemplate(templateForm.id, templateForm)
      ElMessage.success('更新成功')
    } else {
      await createInspectionTemplate(templateForm)
      ElMessage.success('创建成功')
    }
    templateDialogVisible.value = false
    fetchTemplates()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
    else ElMessage.error('操作失败')
  } finally {
    templateSaving.value = false
  }
}

const handleCopyTemplate = async (row) => {
  try {
    await copyInspectionTemplate(row.id, {
      code: `${row.code}_copy`,
      name: `${row.name}(副本)`
    })
    ElMessage.success('模板复制成功')
    fetchTemplates()
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

const handleHandleAbnormal = (row) => {
  currentAbnormal.value = row
  handleForm.notes = ''
  handleDialogVisible.value = true
}

const confirmHandle = async () => {
  if (!handleForm.notes) {
    ElMessage.warning('请输入处理说明')
    return
  }
  
  handleLoading.value = true
  try {
    await handleInspectionAbnormal(currentAbnormal.value.id, {
      notes: handleForm.notes
    })
    ElMessage.success('异常已处理')
    handleDialogVisible.value = false
    fetchUnhandledAbnormal()
  } catch (e) {
    ElMessage.error('处理失败')
  } finally {
    handleLoading.value = false
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getStatusTag = (status) => {
  const tags = { PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', ABNORMAL: 'danger' }
  return tags[status] || 'info'
}

const getAbnormalLevelTag = (level) => {
  const tags = { LOW: 'info', MEDIUM: 'warning', HIGH: 'danger', CRITICAL: 'danger' }
  return tags[level] || ''
}

const getAbnormalLevelText = (level) => {
  const texts = { LOW: '轻微', MEDIUM: '一般', HIGH: '严重', CRITICAL: '紧急' }
  return texts[level] || level
}

onMounted(() => {
  fetchData()
  fetchTemplates()
  fetchEquipments()
  fetchStats()
  fetchUnhandledAbnormal()
})
</script>

<style scoped>
.inspection-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 16px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 6px;
}

.stat-success .stat-value { color: #67c23a; }
.stat-warning .stat-value { color: #e6a23c; }
.stat-danger .stat-value { color: #f56c6c; }

.filter-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
</style>
