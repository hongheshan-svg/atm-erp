<template>
  <div class="equipment-list">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card producing">
          <div class="stat-content">
            <div class="stat-number">{{ stats.by_status?.PRODUCING || 0 }}</div>
            <div class="stat-label">生产中</div>
          </div>
          <el-icon class="stat-icon"><Tools /></el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card installing">
          <div class="stat-content">
            <div class="stat-number">{{ stats.by_status?.INSTALLING || 0 }}</div>
            <div class="stat-label">安装中</div>
          </div>
          <el-icon class="stat-icon"><OfficeBuilding /></el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card warranty">
          <div class="stat-content">
            <div class="stat-number">{{ stats.in_warranty || 0 }}</div>
            <div class="stat-label">质保期内</div>
          </div>
          <el-icon class="stat-icon"><CircleCheck /></el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card expiring">
          <div class="stat-content">
            <div class="stat-number">{{ stats.warranty_expiring_soon || 0 }}</div>
            <div class="stat-label">即将过保</div>
          </div>
          <el-icon class="stat-icon"><Warning /></el-icon>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选工具栏 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="设备状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable>
            <el-option label="生产中" value="PRODUCING" />
            <el-option label="厂内调试" value="TESTING" />
            <el-option label="待发货" value="READY" />
            <el-option label="运输中" value="SHIPPING" />
            <el-option label="现场安装" value="INSTALLING" />
            <el-option label="现场调试" value="COMMISSIONING" />
            <el-option label="已验收" value="ACCEPTED" />
            <el-option label="质保期" value="WARRANTY" />
            <el-option label="质保后" value="POST_WARRANTY" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="filters.customer" placeholder="选择客户" clearable filterable>
            <el-option
              v-for="c in customers"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.search" placeholder="设备编号/名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
          <el-button @click="resetFilters"><el-icon><Refresh /></el-icon> 重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span>设备台账列表</span>
          <el-button type="primary" @click="showDialog('add')">
            <el-icon><Plus /></el-icon> 新增设备
          </el-button>
        </div>
      </template>

      <el-table :data="tableData" stripe v-loading="loading" @row-click="handleRowClick">
        <el-table-column prop="equipment_no" label="设备编号" width="140" />
        <el-table-column prop="name" label="设备名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="model" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="warranty_end_date" label="质保到期" width="110">
          <template #default="{ row }">
            <span :class="{ 'text-danger': isExpiringSoon(row.warranty_end_date) }">
              {{ row.warranty_end_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="installation_address" label="安装地址" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showDetail(row)">详情</el-button>
            <el-button link type="primary" @click.stop="showDialog('edit', row)">编辑</el-button>
            <el-dropdown @click.stop @command="handleCommand($event, row)">
              <el-button link type="primary">更多<el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="ship" :disabled="row.status !== 'READY'">发货</el-dropdown-item>
                  <el-dropdown-item command="install" :disabled="!['SHIPPING', 'INSTALLING'].includes(row.status)">安装</el-dropdown-item>
                  <el-dropdown-item command="accept" :disabled="row.status !== 'COMMISSIONING'">验收</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'add' ? '新增设备' : '编辑设备'"
      width="800px"
      destroy-on-close
    >
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入设备名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格型号" prop="model">
              <el-input v-model="formData.model" placeholder="请输入规格型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属项目" prop="project">
              <el-select v-model="formData.project" placeholder="选择项目" filterable style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="formData.customer" placeholder="选择客户" filterable style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="序列号" prop="serial_no">
              <el-input v-model="formData.serial_no" placeholder="出厂序列号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="质保期" prop="warranty_months">
              <el-input-number v-model="formData.warranty_months" :min="0" :max="120" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="安装地址" prop="installation_address">
          <el-input v-model="formData.installation_address" type="textarea" rows="2" placeholder="设备安装地址" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人" prop="installation_contact">
              <el-input v-model="formData.installation_contact" placeholder="现场联系人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" prop="installation_phone">
              <el-input v-model="formData.installation_phone" placeholder="联系电话" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="notes">
          <el-input v-model="formData.notes" type="textarea" rows="3" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 设备详情抽屉 -->
    <el-drawer v-model="detailVisible" title="设备详情" size="60%">
      <el-descriptions :column="2" border v-if="currentEquipment">
        <el-descriptions-item label="设备编号">{{ currentEquipment.equipment_no }}</el-descriptions-item>
        <el-descriptions-item label="设备名称">{{ currentEquipment.name }}</el-descriptions-item>
        <el-descriptions-item label="规格型号">{{ currentEquipment.model }}</el-descriptions-item>
        <el-descriptions-item label="序列号">{{ currentEquipment.serial_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentEquipment.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ currentEquipment.project_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentEquipment.status)">{{ currentEquipment.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="质保期">{{ currentEquipment.warranty_months }} 个月</el-descriptions-item>
        <el-descriptions-item label="质保开始">{{ currentEquipment.warranty_start_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="质保结束">{{ currentEquipment.warranty_end_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="安装地址" :span="2">{{ currentEquipment.installation_address }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ currentEquipment.installation_contact }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ currentEquipment.installation_phone }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Refresh, Plus, ArrowDown, Tools, OfficeBuilding, CircleCheck, Warning
} from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const dialogMode = ref('add')
const formRef = ref(null)

const stats = ref({})
const tableData = ref([])
const customers = ref([])
const projects = ref([])
const currentEquipment = ref(null)

const filters = reactive({
  status: '',
  customer: '',
  search: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const formData = reactive({
  name: '',
  model: '',
  serial_no: '',
  project: '',
  customer: '',
  warranty_months: 12,
  installation_address: '',
  installation_contact: '',
  installation_phone: '',
  notes: ''
})

const formRules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }
    const res = await request.get('/projects/equipment/', { params })
    tableData.value = res.data.results || res.data
    pagination.total = res.data.count || tableData.value.length
  } catch (error) {
    ElMessage.error('获取设备列表失败')
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const res = await request.get('/projects/equipment/statistics/')
    stats.value = res.data
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const fetchCustomers = async () => {
  try {
    const res = await request.get('/masterdata/customers/')
    customers.value = res.data.results || res.data
  } catch (error) {
    console.error('获取客户失败', error)
  }
}

const fetchProjects = async () => {
  try {
    const res = await request.get('/projects/projects/')
    projects.value = res.data.results || res.data
  } catch (error) {
    console.error('获取项目失败', error)
  }
}

const resetFilters = () => {
  filters.status = ''
  filters.customer = ''
  filters.search = ''
  fetchData()
}

const showDialog = (mode, row = null) => {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    Object.assign(formData, row)
  } else {
    Object.keys(formData).forEach(key => {
      formData[key] = key === 'warranty_months' ? 12 : ''
    })
  }
  dialogVisible.value = true
}

const showDetail = (row) => {
  currentEquipment.value = row
  detailVisible.value = true
}

const handleRowClick = (row) => {
  showDetail(row)
}

const submitForm = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    
    if (dialogMode.value === 'add') {
      await request.post('/projects/equipment/', formData)
      ElMessage.success('新增成功')
    } else {
      await request.put(`/projects/equipment/${formData.id}/`, formData)
      ElMessage.success('更新成功')
    }
    
    dialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (error) {
    if (error !== false) {
      ElMessage.error('操作失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleCommand = async (command, row) => {
  switch (command) {
    case 'ship':
      ElMessage.info('发货功能开发中')
      break
    case 'install':
      ElMessage.info('安装功能开发中')
      break
    case 'accept':
      ElMessage.info('验收功能开发中')
      break
    case 'delete':
      try {
        await ElMessageBox.confirm('确定删除该设备？', '警告', { type: 'warning' })
        await request.delete(`/projects/equipment/${row.id}/`)
        ElMessage.success('删除成功')
        fetchData()
        fetchStats()
      } catch {}
      break
  }
}

const getStatusType = (status) => {
  const types = {
    PRODUCING: 'info',
    TESTING: 'warning',
    READY: 'primary',
    SHIPPING: 'warning',
    INSTALLING: 'warning',
    COMMISSIONING: 'warning',
    ACCEPTED: 'success',
    WARRANTY: 'success',
    POST_WARRANTY: 'info',
    SCRAPPED: 'danger'
  }
  return types[status] || 'info'
}

const isExpiringSoon = (date) => {
  if (!date) return false
  const endDate = new Date(date)
  const now = new Date()
  const diff = (endDate - now) / (1000 * 60 * 60 * 24)
  return diff > 0 && diff <= 30
}

onMounted(() => {
  fetchData()
  fetchStats()
  fetchCustomers()
  fetchProjects()
})
</script>

<style scoped>
.equipment-list {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  overflow: hidden;
}

.stat-card.producing { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.stat-card.installing { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
.stat-card.warranty { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
.stat-card.expiring { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }

.stat-content {
  color: white;
  position: relative;
  z-index: 1;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
  margin-top: 5px;
}

.stat-icon {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 48px;
  opacity: 0.3;
  color: white;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.table-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.text-danger {
  color: #f56c6c;
  font-weight: bold;
}
</style>
