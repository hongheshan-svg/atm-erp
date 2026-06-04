<template>
  <div class="asset-container">
    <div class="page-header">
      <h2>固定资产管理</h2>
      <div class="header-actions">
        <el-button type="primary" v-permission="'finance:fixed_asset:create'" @click="handleAdd">
          <el-icon><Plus /></el-icon>新增资产
        </el-button>
        <el-button @click="handleDepreciate">计提折旧</el-button>
        <el-button @click="handleInventory">资产盘点</el-button>
      </div>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total_count || 0 }}</div>
          <div class="stat-label">资产总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card primary">
          <div class="stat-value">¥{{ formatPrice(stats.total_value) }}</div>
          <div class="stat-label">资产原值</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card warning">
          <div class="stat-value">¥{{ formatPrice(stats.total_depreciation) }}</div>
          <div class="stat-label">累计折旧</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card success">
          <div class="stat-value">¥{{ formatPrice(stats.total_net_value) }}</div>
          <div class="stat-label">资产净值</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card shadow="never">
      <template #header>
        <el-form :inline="true">
          <el-form-item>
            <el-input v-model="queryParams.search" placeholder="搜索资产编号/名称" clearable 
              @clear="fetchList" style="width: 200px" />
          </el-form-item>
          <el-form-item>
            <el-cascader 
              v-model="queryParams.category" 
              :options="categoryTree"
              :props="{ checkStrictly: true, value: 'id', label: 'name', emitPath: false }"
              placeholder="资产分类" 
              clearable 
              @change="fetchList"
              style="width: 180px"
            />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="使用中" value="ACTIVE" />
              <el-option label="闲置" value="IDLE" />
              <el-option label="维修中" value="REPAIRING" />
              <el-option label="已处置" value="DISPOSED" />
              <el-option label="已报废" value="SCRAPPED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.department" placeholder="使用部门" clearable 
              @change="fetchList" style="width: 160px">
              <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchList">查询</el-button>
          </el-form-item>
        </el-form>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="assetList" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="asset_no" label="资产编号" width="120" fixed />
        <el-table-column prop="name" label="资产名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="model" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="110" />
        <el-table-column prop="department_name" label="使用部门" width="110" />
        <el-table-column prop="custodian_name" label="保管人" width="90" />
        <el-table-column prop="original_value" label="原值" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.original_value) }}
          </template>
        </el-table-column>
        <el-table-column prop="accumulated_depreciation" label="累计折旧" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.accumulated_depreciation) }}
          </template>
        </el-table-column>
        <el-table-column prop="net_value" label="净值" width="120" align="right">
          <template #default="{ row }">
            <span :class="{ 'low-value': row.net_value < row.original_value * 0.1 }">
              ¥{{ formatPrice(row.net_value) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="success" link size="small" @click="handleActivate(row)" 
              v-if="row.status === 'DRAFT'">启用</el-button>
            <el-button type="warning" link size="small" @click="handleTransfer(row)" 
              v-if="row.status === 'ACTIVE'">调拨</el-button>
            <el-dropdown v-if="row.status === 'ACTIVE' || row.status === 'IDLE'" trigger="click">
              <el-button type="info" link size="small">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleDispose(row)">处置</el-dropdown-item>
                  <el-dropdown-item @click="handleScrap(row)">报废</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchList"
        @current-change="fetchList"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑资产' : '新增资产'" width="800px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入资产名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产分类" prop="category">
              <el-cascader 
                v-model="formData.category" 
                :options="categoryTree"
                :props="{ checkStrictly: true, value: 'id', label: 'name', emitPath: false }"
                placeholder="选择分类" 
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="规格型号">
              <el-input v-model="formData.model" placeholder="规格型号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="formData.brand" placeholder="品牌" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="序列号">
              <el-input v-model="formData.serial_number" placeholder="序列号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生产厂家">
              <el-input v-model="formData.manufacturer" placeholder="生产厂家" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="购置日期">
              <el-date-picker v-model="formData.purchase_date" type="date" 
                placeholder="购置日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="原值" prop="original_value">
              <el-input-number v-model="formData.original_value" :min="0" :precision="2" 
                style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="使用部门">
              <el-select v-model="formData.department" placeholder="选择部门" style="width: 100%">
                <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保管人">
              <el-select v-model="formData.custodian" placeholder="选择保管人" 
                style="width: 100%" filterable clearable>
                <el-option v-for="u in users" :key="u.id" 
                  :label="u.first_name || u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="存放位置">
          <el-input v-model="formData.location" placeholder="存放位置" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentAsset?.name" width="900px">
      <el-tabs v-if="currentAsset">
        <el-tab-pane label="基本信息">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="资产编号">{{ currentAsset.asset_no }}</el-descriptions-item>
            <el-descriptions-item label="资产名称">{{ currentAsset.name }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ currentAsset.category_name }}</el-descriptions-item>
            <el-descriptions-item label="规格型号">{{ currentAsset.model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="品牌">{{ currentAsset.brand || '-' }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{ currentAsset.serial_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="购置日期">{{ currentAsset.purchase_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="启用日期">{{ currentAsset.start_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentAsset.status)">{{ currentAsset.status_display }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="原值">¥{{ formatPrice(currentAsset.original_value) }}</el-descriptions-item>
            <el-descriptions-item label="累计折旧">¥{{ formatPrice(currentAsset.accumulated_depreciation) }}</el-descriptions-item>
            <el-descriptions-item label="净值">¥{{ formatPrice(currentAsset.net_value) }}</el-descriptions-item>
            <el-descriptions-item label="使用部门">{{ currentAsset.department_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="保管人">{{ currentAsset.custodian_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="存放位置">{{ currentAsset.location || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        
        <el-tab-pane label="折旧记录" v-if="currentAsset.depreciations?.length">
          <el-table :data="currentAsset.depreciations" size="small" border stripe>
            <el-table-column label="期间" width="100">
              <template #default="{ row }">
                {{ row.year }}-{{ String(row.month).padStart(2, '0') }}
              </template>
            </el-table-column>
            <el-table-column prop="opening_net_value" label="期初净值" width="120" align="right">
              <template #default="{ row }">
                ¥{{ formatPrice(row.opening_net_value) }}
              </template>
            </el-table-column>
            <el-table-column prop="depreciation_amount" label="本期折旧" width="120" align="right">
              <template #default="{ row }">
                ¥{{ formatPrice(row.depreciation_amount) }}
              </template>
            </el-table-column>
            <el-table-column prop="closing_net_value" label="期末净值" width="120" align="right">
              <template #default="{ row }">
                ¥{{ formatPrice(row.closing_net_value) }}
              </template>
            </el-table-column>
            <el-table-column prop="is_posted" label="已过账" width="80" align="center">
              <template #default="{ row }">
                <el-icon v-if="row.is_posted" color="#67c23a"><Check /></el-icon>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        
        <el-tab-pane label="变动记录" v-if="currentAsset.transfers?.length">
          <el-timeline>
            <el-timeline-item 
              v-for="change in currentAsset.transfers" 
              :key="change.id"
              :timestamp="change.change_date"
              :type="getChangeType(change.change_type)">
              <div class="change-content">
                <el-tag size="small">{{ change.change_type_display }}</el-tag>
                <span class="change-applicant">{{ change.applicant_name }}</span>
                <p v-if="change.reason">{{ change.reason }}</p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
    
    <!-- 调拨对话框 -->
    <el-dialog v-model="transferDialogVisible" title="资产调拨" width="500px">
      <el-form :model="transferForm" label-width="100px">
        <el-form-item label="资产">
          {{ transferForm.assetName }}
        </el-form-item>
        <el-form-item label="新部门">
          <el-select v-model="transferForm.to_department" placeholder="选择部门" style="width: 100%">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="新保管人">
          <el-select v-model="transferForm.to_custodian" placeholder="选择保管人" 
            style="width: 100%" filterable clearable>
            <el-option v-for="u in users" :key="u.id" 
              :label="u.first_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="新位置">
          <el-input v-model="transferForm.to_location" placeholder="新存放位置" />
        </el-form-item>
        <el-form-item label="调拨原因">
          <el-input v-model="transferForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTransfer" :loading="submitLoading">确认调拨</el-button>
      </template>
    </el-dialog>
    
    <!-- 计提折旧对话框 -->
    <el-dialog v-model="depreciateDialogVisible" title="计提折旧" width="400px">
      <el-form :model="depreciateForm" label-width="80px">
        <el-form-item label="年份">
          <el-input-number v-model="depreciateForm.year" :min="2020" :max="2100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="月份">
          <el-select v-model="depreciateForm.month" style="width: 100%">
            <el-option v-for="m in 12" :key="m" :label="`${m}月`" :value="m" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="depreciateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDepreciate" :loading="submitLoading">开始计提</el-button>
      </template>
    </el-dialog>

    <!-- 资产盘点 -->
    <el-dialog v-model="inventoryDialogVisible" title="资产盘点" width="900px">
      <el-table :data="inventoryResults" v-loading="inventoryLoading" max-height="450">
        <el-table-column width="50">
          <template #default="{ row }">
            <el-checkbox v-model="row.checked" />
          </template>
        </el-table-column>
        <el-table-column prop="asset_code" label="资产编号" width="140" />
        <el-table-column prop="name" label="资产名称" width="160" />
        <el-table-column prop="category_name" label="类别" width="100" />
        <el-table-column prop="department_name" label="部门" width="120" />
        <el-table-column label="是否匹配" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.match" active-text="是" inactive-text="否" />
          </template>
        </el-table-column>
        <el-table-column label="备注">
          <template #default="{ row }">
            <el-input v-model="row.remark" size="small" placeholder="盘点备注" />
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="inventoryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitInventory">提交盘点</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Check } from '@element-plus/icons-vue'
import { getFixedAssets, getFixedAsset, createFixedAsset, patchFixedAsset, getFixedAssetStatistics, getAssetCategories, activateFixedAsset, transferFixedAsset, disposeFixedAsset, scrapFixedAsset, depreciateFixedAssets, inventoryFixedAssets } from '@/api/finance'
import { getDepartments, getUsers } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/finance/fixed-assets/')


const loading = ref(false)
const submitLoading = ref(false)
const assetList = ref<any[]>([])
const stats = ref<Record<string, any>>({})
const categoryTree = ref<any[]>([])
const departments = ref<any[]>([])
const users = ref<any[]>([])

const queryParams = reactive({
  search: '',
  category: null,
  status: null,
  department: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 新增/编辑
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const formData = reactive({
  name: '',
  category: null,
  model: '',
  brand: '',
  serial_number: '',
  manufacturer: '',
  purchase_date: null,
  original_value: 0,
  department: null,
  custodian: null,
  location: '',
  notes: ''
})
const rules = {
  name: [{ required: true, message: '请输入资产名称', trigger: 'blur' }],
  original_value: [{ required: true, message: '请输入原值', trigger: 'blur' }]
}

// 详情
const detailDialogVisible = ref(false)
const currentAsset = ref(null)

// 调拨
const transferDialogVisible = ref(false)
const transferForm = reactive({
  assetId: null,
  assetName: '',
  to_department: null,
  to_custodian: null,
  to_location: '',
  reason: ''
})

// 折旧
const depreciateDialogVisible = ref(false)
const inventoryDialogVisible = ref(false)
const inventoryLoading = ref(false)
const inventoryResults = ref<any[]>([])
const depreciateForm = reactive({
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1
})

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      search: queryParams.search,
      category: queryParams.category,
      status: queryParams.status,
      department: queryParams.department
    }
    const data = await getFixedAssets(params)
    assetList.value = data.results || data || []
    pagination.total = data.count || (Array.isArray(assetList.value) ? assetList.value.length : 0)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const data = await getFixedAssetStatistics()
    stats.value = data.totals || {}
  } catch (e) {
    console.error(e)
  }
}

const fetchOptions = async () => {
  try {
    const [catRes, deptRes, userRes] = await Promise.all([
      getAssetCategories(),
      getDepartments(),
      getUsers()
    ])
    categoryTree.value = catRes.results || catRes || []
    departments.value = deptRes.results || deptRes || []
    users.value = userRes.results || userRes || []
  } catch (e) {
    console.error(e)
  }
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(formData, {
    name: '',
    category: null,
    model: '',
    brand: '',
    serial_number: '',
    manufacturer: '',
    purchase_date: null,
    original_value: 0,
    department: null,
    custodian: null,
    location: '',
    notes: ''
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await patchFixedAsset(currentAsset.value.id, formData)
    } else {
      await createFixedAsset(formData)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const handleView = async (row) => {
  try {
    const data = await getFixedAsset(row.id)
    currentAsset.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

const handleActivate = async (row) => {
  try {
    await ElMessageBox.confirm('确定启用该资产吗？启用后将开始计提折旧', '提示')
    await activateFixedAsset(row.id)
    ElMessage.success('资产已启用')
    fetchList()
    fetchStats()
  } catch (e) {
    console.error('AssetList fetchStats error:', e)
  }
}

const handleTransfer = (row) => {
  transferForm.assetId = row.id
  transferForm.assetName = `${row.asset_no} - ${row.name}`
  transferForm.to_department = null
  transferForm.to_custodian = null
  transferForm.to_location = null
  transferForm.reason = ''
  transferDialogVisible.value = true
}

const submitTransfer = async () => {
  submitLoading.value = true
  try {
    await transferFixedAsset(transferForm.assetId, {
      to_department: transferForm.to_department,
      to_custodian: transferForm.to_custodian,
      to_location: transferForm.to_location,
      reason: transferForm.reason
    })
    ElMessage.success('调拨成功')
    transferDialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('调拨失败')
  } finally {
    submitLoading.value = false
  }
}

const handleDispose = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入处置原因', '资产处置', {
      confirmButtonText: '确认处置',
      cancelButtonText: '取消'
    })
    await disposeFixedAsset(row.id, {
      disposal_reason: value
    })
    ElMessage.success('资产已处置')
    fetchList()
    fetchStats()
  } catch (e) {
    console.error('AssetList fetchStats error:', e)
  }
}

const handleScrap = async (row) => {
  try {
    await ElMessageBox.confirm('确定报废该资产吗？', '资产报废', { type: 'warning' })
    await scrapFixedAsset(row.id)
    ElMessage.success('资产已报废')
    fetchList()
    fetchStats()
  } catch (e) {
    console.error('AssetList fetchStats error:', e)
  }
}

const handleDepreciate = () => {
  depreciateForm.year = new Date().getFullYear()
  depreciateForm.month = new Date().getMonth() + 1
  depreciateDialogVisible.value = true
}

const submitDepreciate = async () => {
  submitLoading.value = true
  try {
    const data = await depreciateFixedAssets({
      year: depreciateForm.year,
      month: depreciateForm.month
    })
    ElMessage.success(`已计提${data.depreciated_count}项资产折旧，共¥${data.total_amount.toFixed(2)}`)
    depreciateDialogVisible.value = false
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error('计提折旧失败')
  } finally {
    submitLoading.value = false
  }
}

const handleInventory = async () => {
  inventoryDialogVisible.value = true
  inventoryLoading.value = true
  try {
    const res = await getFixedAssets({ page_size: 200 })
    const list = res.results || res.results || []
    inventoryResults.value = list.map(a => ({ ...a, checked: false, match: true, remark: '' }))
  } catch (error) {
    console.error(error)
    inventoryResults.value = []
  } finally {
    inventoryLoading.value = false
  }
}

const submitInventory = async () => {
  const items = inventoryResults.value.filter(r => r.checked)
  if (!items.length) return ElMessage.warning('请至少勾选一项')
  try {
    await inventoryFixedAssets({ items: items.map(i => ({ asset_id: i.id, match: i.match, remark: i.remark })) })
    ElMessage.success('盘点提交成功')
    inventoryDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '提交失败')
  }
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    ACTIVE: 'success',
    IDLE: 'warning',
    REPAIRING: 'warning',
    DISPOSED: 'info',
    SCRAPPED: 'danger'
  }
  return types[status] || ''
}

const getChangeType = (changeType) => {
  const types = {
    PURCHASE: 'success',
    TRANSFER: 'primary',
    REPAIR: 'warning',
    UPGRADE: 'success',
    REVALUE: 'primary',
    DISPOSE: 'info',
    SCRAP: 'danger'
  }
  return types[changeType] || ''
}

const formatPrice = (price) => {
  if (!price) return '0.00'
  return Number(price).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(() => {
  fetchOptions()
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.asset-container {
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

.header-actions {
  display: flex;
  gap: 8px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 20px 0;
}

.stat-card .stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-card .stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.stat-card.primary .stat-value { color: #409eff; }
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.success .stat-value { color: #67c23a; }

.low-value {
  color: #f56c6c;
  font-weight: 500;
}

.change-content {
  font-size: 14px;
}

.change-applicant {
  color: #909399;
  margin-left: 8px;
}

.change-content p {
  margin: 4px 0 0 0;
  color: #606266;
}
</style>
