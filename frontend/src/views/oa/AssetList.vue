<template>
  <div class="asset-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>资产管理</span>
          <el-button type="primary" v-permission="'oa:asset:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            添加资产
          </el-button>
        </div>
      </template>
      
      <!-- 统计卡片 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_count || 0 }}</div>
            <div class="stat-label">资产总数</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-value">¥{{ formatNumber(stats.total_purchase_value) }}</div>
            <div class="stat-label">采购总值</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-value">¥{{ formatNumber(stats.total_current_value) }}</div>
            <div class="stat-label">当前价值</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card warning">
            <div class="stat-value">¥{{ formatNumber(stats.depreciation) }}</div>
            <div class="stat-label">累计折旧</div>
          </div>
        </el-col>
      </el-row>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="分类">
          <el-select v-model="searchForm.category" placeholder="选择分类" clearable style="width: 150px;">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="闲置" value="IDLE" />
            <el-option label="使用中" value="IN_USE" />
            <el-option label="维修中" value="REPAIR" />
            <el-option label="已报废" value="SCRAPPED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input v-model="searchForm.search" placeholder="搜索资产编号/名称" clearable style="width: 200px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column prop="asset_no" label="资产编号" width="120" />
        <el-table-column prop="name" label="资产名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="100" />
        <el-table-column label="品牌型号" width="150">
          <template #default="{ row }">{{ row.brand }} {{ row.model }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_user_name" label="使用人" width="100" />
        <el-table-column prop="location" label="位置" width="120" show-overflow-tooltip />
        <el-table-column prop="purchase_price" label="采购价" width="100" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.purchase_price) }}</template>
        </el-table-column>
        <el-table-column prop="current_value" label="当前价值" width="100" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.current_value) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" v-permission="'oa:asset:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'IDLE'" size="small" type="primary" @click="handleAssign(row)">分配</el-button>
            <el-button v-if="row.status === 'IN_USE'" size="small" type="warning" @click="handleReclaim(row)">回收</el-button>
            <el-button size="small" type="info" @click="handleBorrow(row)">借用</el-button>
            <el-button size="small" type="danger" v-permission="'oa:asset:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑资产' : '添加资产'" width="800px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产名称" prop="name">
              <el-input v-model="form.name" placeholder="如：MacBook Pro 14" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产分类" prop="category">
              <el-select v-model="form.category" placeholder="选择分类" style="width: 100%;">
                <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="品牌">
              <el-input v-model="form.brand" placeholder="如：Apple" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="如：M3 Pro" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="规格">
              <el-input v-model="form.specification" placeholder="如：16GB/512GB" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="序列号">
              <el-input v-model="form.serial_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="存放位置">
              <el-input v-model="form.location" placeholder="如：3楼办公室" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">采购信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="购置日期">
              <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="购置价格">
              <el-input-number v-model="form.purchase_price" :min="0" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="保修到期">
              <el-date-picker v-model="form.warranty_expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">折旧设置</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="折旧年限">
              <el-input-number v-model="form.depreciation_years" :min="1" :max="50" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="残值率(%)">
              <el-input-number v-model="form.residual_rate" :min="0" :max="100" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 分配对话框 -->
    <el-dialog v-model="assignDialogVisible" title="分配资产" width="400px">
      <el-form label-width="80px">
        <el-form-item label="分配给">
          <el-select v-model="assignUserId" placeholder="选择用户" filterable style="width: 100%;">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAssign" :loading="saving">确认分配</el-button>
      </template>
    </el-dialog>

    <!-- 借用 -->
    <el-dialog v-model="borrowDialogVisible" title="资产借用" width="500px">
      <el-form label-width="100px">
        <el-form-item label="资产">{{ borrowRow?.name }}</el-form-item>
        <el-form-item label="借用人">
          <el-select v-model="borrowForm.borrower" placeholder="选择借用人" filterable style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="预计归还">
          <el-date-picker v-model="borrowForm.expected_return_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用途">
          <el-input v-model="borrowForm.purpose" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="borrowDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="borrowSaving" @click="handleBorrowSave">确认借用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getAssetCategories, getAssets, createAsset, updateAsset, deleteAsset, getAssetStatistics, assignAsset, reclaimAsset, createAssetBorrow, submitAssetBorrow } from '@/api/oa'
import { getUsers } from '@/api/auth'

const loading = ref(false)
const saving = ref(false)
const borrowDialogVisible = ref(false)
const borrowRow = ref(null)
const borrowForm = reactive({ borrower: null, expected_return_date: '', purpose: '' })
const borrowSaving = ref(false)
const list = ref([])
const categories = ref([])
const users = ref([])
const stats = ref({})
const dialogVisible = ref(false)
const assignDialogVisible = ref(false)
const isEdit = ref(false)
const currentItem = ref(null)
const assignUserId = ref(null)
const formRef = ref(null)

const searchForm = reactive({
  category: null,
  status: '',
  search: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  name: '',
  category: null,
  brand: '',
  model: '',
  specification: '',
  serial_no: '',
  location: '',
  purchase_date: null,
  purchase_price: 0,
  warranty_expire_date: null,
  depreciation_years: 5,
  residual_rate: 5,
  notes: ''
})

const rules = {
  name: [{ required: true, message: '请输入资产名称', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    'IDLE': 'info',
    'IN_USE': 'success',
    'REPAIR': 'warning',
    'SCRAPPED': 'danger',
    'LOST': 'danger'
  }
  return types[status] || 'info'
}

const formatNumber = (num) => {
  if (!num) return '0'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const loadCategories = async () => {
  try {
    const res = await getAssetCategories()
    // res 已经是 response.data
    if (Array.isArray(res)) {
      categories.value = res
    } else if (res && res.results) {
      categories.value = res.results
    } else {
      categories.value = []
    }
  } catch (error) {
    console.error('加载分类失败', error)
  }
}

const loadUsers = async () => {
  try {
    const res = await getUsers({ page_size: 1000 })
    // res 已经是 response.data
    const userData = Array.isArray(res) ? res : (res.results || [])
    users.value = userData.map(u => ({
      id: u.id,
      name: u.name || `${u.last_name}${u.first_name}` || u.username
    }))
  } catch (error) {
    console.error('加载用户失败', error)
  }
}

const loadStats = async () => {
  try {
    const res = await getAssetStatistics()
    // res 已经是 response.data
    stats.value = res || {}
  } catch (error) {
    console.error('加载统计失败', error)
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getAssets(params)
    // res 已经是 response.data
    if (Array.isArray(res)) {
      list.value = res
      pagination.total = res.length
    } else if (res && res.results) {
      list.value = res.results
      pagination.total = res.count || 0
    } else {
      list.value = []
      pagination.total = 0
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, {
    name: '',
    category: null,
    brand: '',
    model: '',
    specification: '',
    serial_no: '',
    location: '',
    purchase_date: null,
    purchase_price: 0,
    warranty_expire_date: null,
    depreciation_years: 5,
    residual_rate: 5,
    notes: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    
    if (isEdit.value) {
      await updateAsset(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createAsset(form)
      ElMessage.success('添加成功')
    }
    
    dialogVisible.value = false
    loadData()
    loadStats()
  } catch (error) {
    if (error.response?.data) {
      ElMessage.error(JSON.stringify(error.response.data))
    }
  } finally {
    saving.value = false
  }
}

const handleAssign = (row) => {
  currentItem.value = row
  assignUserId.value = null
  loadUsers()
  assignDialogVisible.value = true
}

const confirmAssign = async () => {
  if (!assignUserId.value) {
    ElMessage.warning('请选择用户')
    return
  }
  saving.value = true
  try {
    await assignAsset(currentItem.value.id, {
      user_id: assignUserId.value
    })
    ElMessage.success('分配成功')
    assignDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('分配失败')
  } finally {
    saving.value = false
  }
}

const handleReclaim = async (row) => {
  try {
    await ElMessageBox.confirm('确定要回收这个资产吗？', '提示', { type: 'warning' })
    await reclaimAsset(row.id)
    ElMessage.success('回收成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('回收失败')
    }
  }
}

const handleBorrow = (row) => {
  borrowRow.value = row
  Object.assign(borrowForm, { borrower: null, expected_return_date: '', purpose: '' })
  borrowDialogVisible.value = true
}

const handleBorrowSave = async () => {
  borrowSaving.value = true
  try {
    const res = await createAssetBorrow({
      asset: borrowRow.value.id,
      ...borrowForm
    })
    // 自动提交审批
    const borrowId = (res.data || res).id
    if (borrowId) {
      try {
        await submitAssetBorrow(borrowId)
      } catch (e) {
        console.error('AssetList submitAssetBorrow error:', e)
      }
    }
    ElMessage.success('借用成功')
    borrowDialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
    else ElMessage.error('操作失败')
  } finally {
    borrowSaving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这个资产吗？', '提示', { type: 'warning' })
    await deleteAsset(row.id)
    ElMessage.success('删除成功')
    loadData()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadCategories()
  loadStats()
  loadData()
})
</script>

<style scoped>
.asset-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.stat-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.stat-card.warning {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
}

.stat-label {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 5px;
}
</style>
