<template>
  <div class="fixture-list">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card total">
          <div class="stat-content">
            <div class="stat-number">{{ stats.total || 0 }}</div>
            <div class="stat-label">工装总数</div>
          </div>
          <el-icon class="stat-icon"><Box /></el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card in-use">
          <div class="stat-content">
            <div class="stat-number">{{ stats.by_status?.IN_USE || 0 }}</div>
            <div class="stat-label">使用中</div>
          </div>
          <el-icon class="stat-icon"><Aim /></el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card idle">
          <div class="stat-content">
            <div class="stat-number">{{ stats.by_status?.IDLE || 0 }}</div>
            <div class="stat-label">闲置</div>
          </div>
          <el-icon class="stat-icon"><Clock /></el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card calibration">
          <div class="stat-content">
            <div class="stat-number">{{ stats.calibration_due || 0 }}</div>
            <div class="stat-label">待校验</div>
          </div>
          <el-icon class="stat-icon"><Compass /></el-icon>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选工具栏 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable>
            <el-option label="使用中" value="IN_USE" />
            <el-option label="闲置" value="IDLE" />
            <el-option label="维修中" value="REPAIR" />
            <el-option label="已报废" value="SCRAPED" />
            <el-option label="外借" value="LENT" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-cascader
            v-model="filters.category"
            :options="categoryTree"
            :props="{ checkStrictly: true, value: 'id', label: 'name' }"
            placeholder="选择分类"
            clearable
          />
        </el-form-item>
        <el-form-item label="需校验">
          <el-select v-model="filters.needs_calibration" placeholder="全部" clearable>
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.search" placeholder="编号/名称/型号" clearable />
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
          <span>工装夹具列表</span>
          <div>
            <el-button @click="showCategoryDialog">
              <el-icon><Folder /></el-icon> 分类管理
            </el-button>
            <el-button type="primary" @click="showDialog('add')">
              <el-icon><Plus /></el-icon> 新增工装
            </el-button>
          </div>
        </div>
      </template>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table :data="tableData" stripe v-loading="loading" @row-click="handleRowClick" @selection-change="handleSelectionChange">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="fixture_no" label="工装编号" width="140" />
        <el-table-column prop="name" label="工装名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="model" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="100" />
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="存放位置" width="120" show-overflow-tooltip />
        <el-table-column prop="custodian_name" label="保管人" width="90" />
        <el-table-column label="校验" width="100">
          <template #default="{ row }">
            <template v-if="row.needs_calibration">
              <el-tag :type="row.is_calibration_due ? 'danger' : 'success'" size="small">
                {{ row.next_calibration || '待校验' }}
              </el-tag>
            </template>
            <span v-else class="text-muted">无需校验</span>
          </template>
        </el-table-column>
        <el-table-column prop="usage_count" label="使用次数" width="90" align="center" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showDetail(row)">详情</el-button>
            <el-button link type="primary" @click.stop="showDialog('edit', row)">编辑</el-button>
            <el-dropdown @click.stop @command="handleCommand($event, row)">
              <el-button link type="primary">更多<el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="checkout" :disabled="!['IDLE', 'IN_USE'].includes(row.status)">领用</el-dropdown-item>
                  <el-dropdown-item command="return">归还</el-dropdown-item>
                  <el-dropdown-item command="calibrate" :disabled="!row.needs_calibration">校验</el-dropdown-item>
                  <el-dropdown-item command="maintain">维护</el-dropdown-item>
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
      :title="dialogMode === 'add' ? '新增工装' : '编辑工装'"
      width="800px"
      destroy-on-close
    >
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工装名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入工装名称" />
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
            <el-form-item label="分类" prop="category">
              <el-cascader
                v-model="formData.category"
                :options="categoryTree"
                :props="{ checkStrictly: true, value: 'id', label: 'name', emitPath: false }"
                placeholder="选择分类"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所有权" prop="ownership">
              <el-select v-model="formData.ownership" style="width: 100%">
                <el-option label="自有" value="SELF" />
                <el-option label="客户" value="CUSTOMER" />
                <el-option label="借用" value="BORROWED" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="存放位置" prop="location">
              <el-input v-model="formData.location" placeholder="存放位置" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保管人" prop="custodian">
              <el-select v-model="formData.custodian" placeholder="选择保管人" clearable filterable style="width: 100%">
                <el-option v-for="u in users" :key="u.id" :label="u.name || u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="图纸编号" prop="drawing_no">
              <el-input v-model="formData.drawing_no" placeholder="图纸编号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成本价值" prop="purchase_cost">
              <el-input-number v-model="formData.purchase_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="需要校验" prop="needs_calibration">
              <el-switch v-model="formData.needs_calibration" />
            </el-form-item>
          </el-col>
          <el-col :span="8" v-if="formData.needs_calibration">
            <el-form-item label="校验周期" prop="calibration_cycle">
              <el-input-number v-model="formData.calibration_cycle" :min="1" :max="60" style="width: 100%">
                <template #append>月</template>
              </el-input-number>
            </el-form-item>
          </el-col>
          <el-col :span="8" v-if="formData.needs_calibration">
            <el-form-item label="校验机构" prop="calibration_org">
              <el-input v-model="formData.calibration_org" placeholder="校验机构" />
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

    <!-- 分类管理对话框 -->
    <el-dialog v-model="categoryDialogVisible" title="工装分类管理" width="600px">
      <div class="category-header">
        <el-button type="primary" size="small" @click="addCategory">
          <el-icon><Plus /></el-icon> 新增分类
        </el-button>
      </div>
      <el-table :data="flatCategories" row-key="id" default-expand-all :tree-props="{ children: 'children' }">
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editCategory(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteCategory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 工装详情抽屉 -->
    <el-drawer v-model="detailVisible" title="工装详情" size="50%">
      <el-descriptions :column="2" border v-if="currentFixture">
        <el-descriptions-item label="工装编号">{{ currentFixture.fixture_no }}</el-descriptions-item>
        <el-descriptions-item label="工装名称">{{ currentFixture.name }}</el-descriptions-item>
        <el-descriptions-item label="规格型号">{{ currentFixture.model }}</el-descriptions-item>
        <el-descriptions-item label="分类">{{ currentFixture.category_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentFixture.status)">{{ currentFixture.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="所有权">{{ currentFixture.ownership_display }}</el-descriptions-item>
        <el-descriptions-item label="存放位置">{{ currentFixture.location }}</el-descriptions-item>
        <el-descriptions-item label="保管人">{{ currentFixture.custodian_name }}</el-descriptions-item>
        <el-descriptions-item label="图纸编号">{{ currentFixture.drawing_no }}</el-descriptions-item>
        <el-descriptions-item label="成本价值">¥{{ currentFixture.purchase_cost }}</el-descriptions-item>
        <el-descriptions-item label="使用次数">{{ currentFixture.usage_count }}</el-descriptions-item>
        <el-descriptions-item label="最大使用次数">{{ currentFixture.max_usage || '无限制' }}</el-descriptions-item>
        <el-descriptions-item label="需要校验">{{ currentFixture.needs_calibration ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="下次校验" v-if="currentFixture.needs_calibration">
          {{ currentFixture.next_calibration || '待设置' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-drawer>
    <!-- 校验对话框 -->
    <el-dialog v-model="calibrateDialogVisible" title="工装校验" width="500px">
      <el-form label-width="100px">
        <el-form-item label="校验日期">
          <el-date-picker v-model="calibrateForm.calibration_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="校验结果">
          <el-select v-model="calibrateForm.result" style="width: 100%">
            <el-option label="合格" value="PASS" />
            <el-option label="不合格" value="FAIL" />
            <el-option label="需调整" value="ADJUST" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="calibrateForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="calibrateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="opSaving" @click="handleCalibrateSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 维护对话框 -->
    <el-dialog v-model="maintainDialogVisible" title="工装维护" width="500px">
      <el-form label-width="100px">
        <el-form-item label="维护日期">
          <el-date-picker v-model="maintainForm.maintenance_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="维护类型">
          <el-select v-model="maintainForm.maintenance_type" style="width: 100%">
            <el-option label="日常保养" value="ROUTINE" />
            <el-option label="维修" value="REPAIR" />
            <el-option label="更换零件" value="REPLACE_PARTS" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="maintainForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="费用">
          <el-input-number v-model="maintainForm.cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="maintainDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="opSaving" @click="handleMaintainSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Refresh, Plus, ArrowDown, Box, Aim, Clock, Compass, Folder
} from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/fixtures/',
  { onSuccess: () => { fetchData(); fetchStats() }, confirmTitle: '删除工装', confirmMessage: '确定要删除该工装吗？' }
)

const loading = ref(false)
const calibrateDialogVisible = ref(false)
const maintainDialogVisible = ref(false)
const opRow = ref(null)
const calibrateForm = reactive({ calibration_date: '', result: 'PASS', notes: '' })
const maintainForm = reactive({ maintenance_date: '', maintenance_type: 'ROUTINE', description: '', cost: 0 })
const opSaving = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const categoryDialogVisible = ref(false)
const detailVisible = ref(false)
const dialogMode = ref('add')
const formRef = ref(null)

const stats = ref({})
const tableData = ref([])
const categoryTree = ref([])
const flatCategories = ref([])
const users = ref([])
const currentFixture = ref(null)

const filters = reactive({
  status: '',
  category: [],
  needs_calibration: '',
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
  category: null,
  ownership: 'SELF',
  location: '',
  custodian: null,
  drawing_no: '',
  purchase_cost: 0,
  needs_calibration: false,
  calibration_cycle: 12,
  calibration_org: '',
  notes: ''
})

const formRules = {
  name: [{ required: true, message: '请输入工装名称', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      status: filters.status,
      needs_calibration: filters.needs_calibration,
      search: filters.search
    }
    if (filters.category?.length) {
      params.category = filters.category[filters.category.length - 1]
    }
    const res = await request.get('/projects/fixtures/', { params })
    tableData.value = res.results || res || []
    pagination.total = res.count || tableData.value.length
  } catch (error) {
    ElMessage.error('获取工装列表失败')
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const res = await request.get('/projects/fixtures/statistics/')
    stats.value = res || {}
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const fetchCategories = async () => {
  try {
    const res = await request.get('/projects/fixture-categories/tree/')
    categoryTree.value = res || []
    
    const flatRes = await request.get('/projects/fixture-categories/')
    flatCategories.value = flatRes.results || flatRes || []
  } catch (error) {
    console.error('获取分类失败', error)
  }
}

const fetchUsers = async () => {
  try {
    const res = await request.get('/auth/users/')
    users.value = res.results || res || []
  } catch (error) {
    console.error('获取用户失败', error)
  }
}

const resetFilters = () => {
  filters.status = ''
  filters.category = []
  filters.needs_calibration = ''
  filters.search = ''
  fetchData()
}

const showDialog = (mode, row = null) => {
  dialogMode.value = mode
  if (mode === 'edit' && row) {
    Object.assign(formData, row)
  } else {
    Object.keys(formData).forEach(key => {
      if (key === 'ownership') formData[key] = 'SELF'
      else if (key === 'purchase_cost') formData[key] = 0
      else if (key === 'needs_calibration') formData[key] = false
      else if (key === 'calibration_cycle') formData[key] = 12
      else if (key === 'category' || key === 'custodian') formData[key] = null
      else formData[key] = ''
    })
  }
  dialogVisible.value = true
}

const showDetail = (row) => {
  currentFixture.value = row
  detailVisible.value = true
}

const handleRowClick = (row) => {
  showDetail(row)
}

const showCategoryDialog = () => {
  categoryDialogVisible.value = true
}

const addCategory = async () => {
  const { value } = await ElMessageBox.prompt('请输入分类名称', '新增分类', {
    inputPattern: /.+/,
    inputErrorMessage: '分类名称不能为空'
  })
  
  try {
    const code = 'CAT' + Date.now().toString().slice(-6)
    await request.post('/projects/fixture-categories/', { code, name: value })
    ElMessage.success('新增成功')
    fetchCategories()
  } catch (error) {
    ElMessage.error('新增失败')
  }
}

const editCategory = async (row) => {
  const { value } = await ElMessageBox.prompt('请输入分类名称', '编辑分类', {
    inputValue: row.name,
    inputPattern: /.+/,
    inputErrorMessage: '分类名称不能为空'
  })
  
  try {
    await request.patch(`/projects/fixture-categories/${row.id}/`, { name: value })
    ElMessage.success('更新成功')
    fetchCategories()
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const deleteCategory = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该分类？', '警告', { type: 'warning' })
    await request.delete(`/projects/fixture-categories/${row.id}/`)
    ElMessage.success('删除成功')
    fetchCategories()
  } catch {}
}

const submitForm = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    
    if (dialogMode.value === 'add') {
      await request.post('/projects/fixtures/', formData)
      ElMessage.success('新增成功')
    } else {
      await request.put(`/projects/fixtures/${formData.id}/`, formData)
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
    case 'checkout':
      try {
        await request.post(`/projects/fixtures/${row.id}/checkout/`, {
          purpose: '项目使用'
        })
        ElMessage.success('领用成功')
        fetchData()
        fetchStats()
      } catch (error) {
        ElMessage.error('领用失败')
      }
      break
    case 'return':
      try {
        await request.post(`/projects/fixtures/${row.id}/return_fixture/`, {
          condition: '良好'
        })
        ElMessage.success('归还成功')
        fetchData()
        fetchStats()
      } catch (error) {
        ElMessage.error('归还失败')
      }
      break
    case 'calibrate':
      opRow.value = row
      Object.assign(calibrateForm, { calibration_date: new Date().toISOString().split('T')[0], result: 'PASS', notes: '' })
      calibrateDialogVisible.value = true
      break
    case 'maintain':
      opRow.value = row
      Object.assign(maintainForm, { maintenance_date: new Date().toISOString().split('T')[0], maintenance_type: 'ROUTINE', description: '', cost: 0 })
      maintainDialogVisible.value = true
      break
    case 'delete':
      if (canDelete.value) {
        deleteRow(row)
      } else {
        ElMessage.warning('您没有删除权限')
      }
      break
  }
}


const handleCalibrateSave = async () => {
  opSaving.value = true
  try {
    await request.post(`/projects/fixtures/${opRow.value.id}/calibrate/`, calibrateForm)
    ElMessage.success('校验记录已保存')
    calibrateDialogVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    opSaving.value = false
  }
}

const handleMaintainSave = async () => {
  opSaving.value = true
  try {
    await request.post(`/projects/fixtures/${opRow.value.id}/maintain/`, maintainForm)
    ElMessage.success('维护记录已保存')
    maintainDialogVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    opSaving.value = false
  }
}

const getStatusType = (status) => {
  const types = {
    IN_USE: 'success',
    IDLE: 'info',
    REPAIR: 'warning',
    SCRAPED: 'danger',
    LENT: 'warning'
  }
  return types[status] || 'info'
}

onMounted(() => {
  fetchData()
  fetchStats()
  fetchCategories()
  fetchUsers()
})
</script>

<style scoped>
.fixture-list {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  overflow: hidden;
}

.stat-card.total { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.stat-card.in-use { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
.stat-card.idle { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
.stat-card.calibration { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }

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

.category-header {
  margin-bottom: 15px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.text-muted {
  color: #999;
  font-size: 12px;
}
</style>
