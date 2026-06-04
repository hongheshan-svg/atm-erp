<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>设备档案管理</span>
          <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd">
            <el-icon><Plus /></el-icon> 新增设备档案
          </el-button>
        </div>
      </template>
      
      <!-- 统计卡片 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="4">
          <el-statistic title="设备总数" :value="stats.total" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="生产中" :value="stats.manufacturing" :value-style="{ color: '#409eff' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="运行中" :value="stats.running" :value-style="{ color: '#67c23a' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="维护中" :value="stats.maintenance" :value-style="{ color: '#e6a23c' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已交付" :value="stats.delivered" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="即将过保" :value="stats.warranty_expiring" :value-style="{ color: '#f56c6c' }" />
        </el-col>
      </el-row>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="设备编号">
          <el-input v-model="searchForm.equipment_no" placeholder="设备编号" clearable />
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="searchForm.equipment_type" placeholder="选择类型" clearable>
            <el-option label="组装线" value="ASSEMBLY_LINE" />
            <el-option label="检测设备" value="TESTING_EQUIPMENT" />
            <el-option label="加工设备" value="PROCESSING_EQUIPMENT" />
            <el-option label="搬运设备" value="HANDLING_EQUIPMENT" />
            <el-option label="包装设备" value="PACKAGING_EQUIPMENT" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="生产中" value="MANUFACTURING" />
            <el-option label="调试中" value="TESTING" />
            <el-option label="已交付" value="DELIVERED" />
            <el-option label="已安装" value="INSTALLED" />
            <el-option label="运行中" value="RUNNING" />
            <el-option label="维护中" value="MAINTENANCE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 数据表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="equipment_no" label="设备编号" width="130" />
        <el-table-column prop="serial_number" label="出厂序列号" width="150" />
        <el-table-column prop="name" label="设备名称" min-width="180" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="type_display" label="类型" width="100" />
        <el-table-column prop="project_name" label="项目" width="150" />
        <el-table-column prop="customer_name" label="客户" width="120" />
        <el-table-column prop="manufacture_date" label="制造日期" width="110" />
        <el-table-column prop="warranty_end_date" label="质保到期" width="110">
          <template #default="{ row }">
            <el-tag v-if="isWarrantyExpiring(row.warranty_end_date)" type="danger">
              {{ row.warranty_end_date }}
            </el-tag>
            <span v-else>{{ row.warranty_end_date || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="primary" link size="small" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link size="small" @click="handleNameplate(row)">铭牌</el-button>
            <el-button type="warning" link size="small" @click="handleMaintenance(row)">维保</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px;"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="formData" :rules="formRules" ref="formRef" label-width="120px">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="设备编号" prop="equipment_no">
                  <el-input v-model="formData.equipment_no" placeholder="设备编号" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="出厂序列号" prop="serial_number">
                  <el-input v-model="formData.serial_number" placeholder="出厂序列号" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="设备名称" prop="name">
                  <el-input v-model="formData.name" placeholder="设备名称" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="设备型号" prop="model">
                  <el-input v-model="formData.model" placeholder="设备型号" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="设备类型" prop="equipment_type">
                  <el-select v-model="formData.equipment_type" placeholder="选择类型" style="width: 100%;">
                    <el-option label="组装线" value="ASSEMBLY_LINE" />
                    <el-option label="检测设备" value="TESTING_EQUIPMENT" />
                    <el-option label="加工设备" value="PROCESSING_EQUIPMENT" />
                    <el-option label="搬运设备" value="HANDLING_EQUIPMENT" />
                    <el-option label="包装设备" value="PACKAGING_EQUIPMENT" />
                    <el-option label="检查设备" value="INSPECTION_EQUIPMENT" />
                    <el-option label="其他" value="OTHER" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="制造日期" prop="manufacture_date">
                  <el-date-picker v-model="formData.manufacture_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="关联项目" prop="project">
                  <el-select v-model="formData.project" placeholder="选择项目" style="width: 100%;" filterable>
                    <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="客户" prop="customer">
                  <el-select v-model="formData.customer" placeholder="选择客户" style="width: 100%;" filterable>
                    <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="铭牌信息" name="nameplate">
          <el-form :model="formData" label-width="120px">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="制造商">
                  <el-input v-model="formData.manufacturer" placeholder="制造商" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="额定功率">
                  <el-input v-model="formData.rated_power" placeholder="如: 5kW" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="额定电压">
                  <el-input v-model="formData.rated_voltage" placeholder="如: 380V" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="额定电流">
                  <el-input v-model="formData.rated_current" placeholder="如: 15A" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="设备重量(kg)">
                  <el-input-number v-model="formData.weight" :min="0" style="width: 100%;" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="外形尺寸">
                  <el-input v-model="formData.dimensions" placeholder="如: 2000×1500×1800mm" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="质保信息" name="warranty">
          <el-form :model="formData" label-width="120px">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="质保开始日期">
                  <el-date-picker v-model="formData.warranty_start_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="质保结束日期">
                  <el-date-picker v-model="formData.warranty_end_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="质保条款">
              <el-input v-model="formData.warranty_terms" type="textarea" :rows="4" placeholder="质保条款说明" />
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="安装日期">
                  <el-date-picker v-model="formData.installation_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="验收日期">
                  <el-date-picker v-model="formData.acceptance_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="安装地址">
              <el-input v-model="formData.installation_address" type="textarea" :rows="2" placeholder="设备安装地址" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 铭牌对话框 -->
    <el-dialog v-model="nameplateVisible" title="设备铭牌" width="600px">
      <div class="nameplate-card" v-if="currentEquipment">
        <div class="nameplate-header">
          <h2>{{ currentEquipment.manufacturer }}</h2>
        </div>
        <div class="nameplate-body">
          <div class="nameplate-row">
            <span class="label">设备名称:</span>
            <span class="value">{{ currentEquipment.name }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">设备型号:</span>
            <span class="value">{{ currentEquipment.model }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">出厂序列号:</span>
            <span class="value">{{ currentEquipment.serial_number }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">制造日期:</span>
            <span class="value">{{ currentEquipment.manufacture_date }}</span>
          </div>
          <el-divider />
          <div class="nameplate-row">
            <span class="label">额定功率:</span>
            <span class="value">{{ currentEquipment.rated_power || '-' }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">额定电压:</span>
            <span class="value">{{ currentEquipment.rated_voltage || '-' }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">额定电流:</span>
            <span class="value">{{ currentEquipment.rated_current || '-' }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">设备重量:</span>
            <span class="value">{{ currentEquipment.weight ? currentEquipment.weight + ' kg' : '-' }}</span>
          </div>
          <div class="nameplate-row">
            <span class="label">外形尺寸:</span>
            <span class="value">{{ currentEquipment.dimensions || '-' }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="nameplateVisible = false">关闭</el-button>
        <el-button type="primary" @click="printNameplate">打印</el-button>
      </template>
    </el-dialog>
    <!-- 维保记录 -->
    <el-dialog v-model="maintDialogVisible" :title="'维保记录 - ' + (currentEquipment?.equipment_no || '')" width="700px">
      <el-table :data="maintRecords" v-loading="maintLoading" stripe>
        <el-table-column prop="maintenance_date" label="维保日期" width="120" />
        <el-table-column prop="maintenance_type_display" label="类型" width="100" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="cost" label="费用" width="100" align="right">
          <template #default="{ row }">¥{{ row.cost?.toLocaleString() || 0 }}</template>
        </el-table-column>
        <el-table-column prop="performed_by_name" label="执行人" width="100" />
        <el-table-column prop="next_date" label="下次维保" width="120" />
      </el-table>
      <el-empty v-if="!maintLoading && maintRecords.length === 0" description="暂无维保记录" />
      <template #footer>
        <el-button @click="maintDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getEquipmentArchiveList, createEquipmentArchive, updateEquipmentArchive, getEquipmentArchiveStatistics, getEquipmentArchiveNameplate, getEquipmentArchiveMaintenanceRecords } from '@/api/projects/equipment-monitoring'
import { getProjectList } from '@/api/projects/project'
import { getCustomerList } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/equipment-archives/', { onSuccess: () => loadData() })


const loading = ref(false)
const maintDialogVisible = ref(false)
const maintRecords = ref<any[]>([])
const maintLoading = ref(false)
const currentEquipment = ref(null)
const tableData = ref<any[]>([])
const projects = ref<any[]>([])
const customers = ref<any[]>([])
const dialogVisible = ref(false)
const nameplateVisible = ref(false)
const dialogTitle = ref('新增设备档案')
const formRef = ref(null)
const activeTab = ref('basic')

const stats = reactive({
  total: 0,
  manufacturing: 0,
  running: 0,
  maintenance: 0,
  delivered: 0,
  warranty_expiring: 0
})

const searchForm = reactive({
  equipment_no: '',
  equipment_type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const formData = reactive({
  id: null,
  equipment_no: '',
  serial_number: '',
  name: '',
  model: '',
  equipment_type: 'ASSEMBLY_LINE',
  manufacture_date: '',
  project: null,
  customer: null,
  manufacturer: '深圳市奥特迈智能装备有限公司',
  rated_power: '',
  rated_voltage: '',
  rated_current: '',
  weight: null,
  dimensions: '',
  warranty_start_date: '',
  warranty_end_date: '',
  warranty_terms: '',
  installation_date: '',
  acceptance_date: '',
  installation_address: ''
})

const formRules = {
  equipment_no: [{ required: true, message: '请输入设备编号', trigger: 'blur' }],
  serial_number: [{ required: true, message: '请输入出厂序列号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  model: [{ required: true, message: '请输入设备型号', trigger: 'blur' }],
  equipment_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  manufacture_date: [{ required: true, message: '请选择制造日期', trigger: 'change' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = {
    'MANUFACTURING': 'info',
    'TESTING': 'warning',
    'DELIVERED': 'success',
    'INSTALLED': 'success',
    'RUNNING': 'success',
    'MAINTENANCE': 'warning',
    'DECOMMISSIONED': 'danger'
  }
  return types[status] || 'info'
}

const isWarrantyExpiring = (date) => {
  if (!date) return false
  const warrantyDate = new Date(date)
  const today = new Date()
  const diffDays = (warrantyDate - today) / (1000 * 60 * 60 * 24)
  return diffDays <= 30 && diffDays >= 0
}

const loadData = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getEquipmentArchiveList(params)
    tableData.value = res.results || res
    pagination.total = res.count || tableData.value.length
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await getEquipmentArchiveStatistics()
    stats.total = res.total || 0
    stats.manufacturing = res.by_status?.MANUFACTURING?.count || 0
    stats.running = res.by_status?.RUNNING?.count || 0
    stats.maintenance = res.by_status?.MAINTENANCE?.count || 0
    stats.delivered = res.by_status?.DELIVERED?.count || 0
    stats.warranty_expiring = res.warranty_expiring_30_days || 0
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.results || res
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 1000 })
    customers.value = res.results || res
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const resetSearch = () => {
  searchForm.equipment_no = ''
  searchForm.equipment_type = ''
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

const resetForm = () => {
  Object.keys(formData).forEach(key => {
    if (key === 'manufacturer') {
      formData[key] = '深圳市奥特迈智能装备有限公司'
    } else if (key === 'equipment_type') {
      formData[key] = 'ASSEMBLY_LINE'
    } else {
      formData[key] = null
    }
  })
  activeTab.value = 'basic'
}

const handleAdd = () => {
  resetForm()
  dialogTitle.value = '新增设备档案'
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(formData, row)
  dialogTitle.value = '编辑设备档案'
  dialogVisible.value = true
}

const handleView = (row) => {
  Object.assign(formData, row)
  dialogTitle.value = '查看设备档案'
  dialogVisible.value = true
}

const handleNameplate = async (row) => {
  try {
    const res = await getEquipmentArchiveNameplate(row.id)
    currentEquipment.value = { ...row, ...res }
    nameplateVisible.value = true
  } catch (error) {
    currentEquipment.value = row
    nameplateVisible.value = true
  }
}

const handleMaintenance = async (row) => {
  currentEquipment.value = row
  maintDialogVisible.value = true
  maintLoading.value = true
  try {
    const res = await getEquipmentArchiveMaintenanceRecords(row.id)
    maintRecords.value = res.results || res.results || res || []
  } catch (error) {
    console.error(error)
    maintRecords.value = []
  } finally {
    maintLoading.value = false
  }
}

const printNameplate = () => {
  window.print()
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (formData.id) {
      await updateEquipmentArchive(formData.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createEquipmentArchive(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
    loadStats()
  } catch (error) {
    console.error('保存失败:', error)
  }
}

onMounted(() => {
  loadData()
  loadStats()
  loadProjects()
  loadCustomers()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.search-form {
  margin-bottom: 20px;
}

.nameplate-card {
  border: 2px solid #333;
  border-radius: 8px;
  padding: 20px;
  background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
}

.nameplate-header {
  text-align: center;
  border-bottom: 2px solid #333;
  padding-bottom: 15px;
  margin-bottom: 15px;
}

.nameplate-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: bold;
}

.nameplate-body {
  font-size: 14px;
}

.nameplate-row {
  display: flex;
  margin-bottom: 10px;
}

.nameplate-row .label {
  width: 100px;
  font-weight: bold;
  color: #333;
}

.nameplate-row .value {
  flex: 1;
  color: #666;
}

@media print {
  .page-container > * {
    display: none;
  }
  .nameplate-card {
    display: block !important;
  }
}
</style>
