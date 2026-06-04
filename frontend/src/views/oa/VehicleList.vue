<template>
  <div class="vehicle-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>车辆管理</span>
          <el-button type="primary" v-permission="'oa:vehicle:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            添加车辆
          </el-button>
        </div>
      </template>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="车型">
          <el-select v-model="searchForm.vehicle_type" placeholder="选择类型" clearable style="width: 120px;">
            <el-option label="轿车" value="CAR" />
            <el-option label="SUV" value="SUV" />
            <el-option label="面包车" value="VAN" />
            <el-option label="货车" value="TRUCK" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="可用" value="AVAILABLE" />
            <el-option label="使用中" value="IN_USE" />
            <el-option label="维护中" value="MAINTENANCE" />
            <el-option label="停用" value="DISABLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="list" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="plate_number" label="车牌号" width="120" />
        <el-table-column prop="type_display" label="车型" width="80" />
        <el-table-column label="品牌型号" width="150">
          <template #default="{ row }">{{ row.brand }} {{ row.model }}</template>
        </el-table-column>
        <el-table-column prop="color" label="颜色" width="80" />
        <el-table-column prop="seats" label="座位" width="60" align="center" />
        <el-table-column prop="current_mileage" label="里程(km)" width="100" align="right" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="insurance_expire_date" label="保险到期" width="110" />
        <el-table-column prop="next_inspection_date" label="年检到期" width="110" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" v-permission="'oa:vehicle:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="primary" @click="handleMaintenance(row)">维护记录</el-button>
            <el-button size="small" type="danger" v-permission="'oa:vehicle:delete'" @click="handleDelete(row)">删除</el-button>
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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑车辆' : '添加车辆'" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="车牌号" prop="plate_number">
              <el-input v-model="form.plate_number" placeholder="如：沪A12345" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="车型" prop="vehicle_type">
              <el-select v-model="form.vehicle_type" style="width: 100%;">
                <el-option label="轿车" value="CAR" />
                <el-option label="SUV" value="SUV" />
                <el-option label="面包车" value="VAN" />
                <el-option label="货车" value="TRUCK" />
                <el-option label="大巴" value="BUS" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="品牌" prop="brand">
              <el-input v-model="form.brand" placeholder="如：大众" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号" prop="model">
              <el-input v-model="form.model" placeholder="如：帕萨特" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="颜色">
              <el-input v-model="form.color" placeholder="如：白色" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="座位数">
              <el-input-number v-model="form.seats" :min="1" :max="50" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="当前里程">
              <el-input-number v-model="form.current_mileage" :min="0" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="发动机号">
              <el-input v-model="form.engine_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="车架号">
              <el-input v-model="form.vin" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">保险信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="保险公司">
              <el-input v-model="form.insurance_company" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保险到期">
              <el-date-picker v-model="form.insurance_expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="年检日期">
              <el-date-picker v-model="form.annual_inspection_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="下次年检">
              <el-date-picker v-model="form.next_inspection_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
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

    <!-- 维护记录 -->
    <el-dialog v-model="maintDialogVisible" :title="'维护记录 - ' + (currentVehicle?.plate_number || '')" width="700px">
      <el-table :data="maintRecords" v-loading="maintLoading" stripe>
        <el-table-column prop="maintenance_date" label="维护日期" width="120" />
        <el-table-column prop="maintenance_type_display" label="类型" width="100" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="cost" label="费用" width="100" align="right">
          <template #default="{ row }">¥{{ row.cost?.toLocaleString() || 0 }}</template>
        </el-table-column>
        <el-table-column prop="service_provider" label="服务商" width="120" />
        <el-table-column prop="next_maintenance_date" label="下次维护" width="120" />
      </el-table>
      <el-empty v-if="!maintLoading && maintRecords.length === 0" description="暂无维护记录" />
      <template #footer>
        <el-button @click="maintDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getVehicles, createVehicle, updateVehicle, deleteVehicle, getVehicleMaintenanceRecords } from '@/api/oa'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/oa/vehicles/', { onSuccess: () => loadData() })


const loading = ref(false)
const saving = ref(false)
const maintDialogVisible = ref(false)
const maintRecords = ref<any[]>([])
const maintLoading = ref(false)
const currentVehicle = ref(null)
const list = ref<any[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  vehicle_type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  plate_number: '',
  vehicle_type: 'CAR',
  brand: '',
  model: '',
  color: '',
  seats: 5,
  engine_no: '',
  vin: '',
  insurance_company: '',
  insurance_expire_date: null,
  annual_inspection_date: null,
  next_inspection_date: null,
  current_mileage: 0,
  notes: ''
})

const rules = {
  plate_number: [{ required: true, message: '请输入车牌号', trigger: 'blur' }],
  vehicle_type: [{ required: true, message: '请选择车型', trigger: 'change' }],
  brand: [{ required: true, message: '请输入品牌', trigger: 'blur' }],
  model: [{ required: true, message: '请输入型号', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    'AVAILABLE': 'success',
    'IN_USE': 'primary',
    'MAINTENANCE': 'warning',
    'DISABLED': 'danger'
  }
  return types[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getVehicles(params)
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
    plate_number: '',
    vehicle_type: 'CAR',
    brand: '',
    model: '',
    color: '',
    seats: 5,
    engine_no: '',
    vin: '',
    insurance_company: '',
    insurance_expire_date: null,
    annual_inspection_date: null,
    next_inspection_date: null,
    current_mileage: 0,
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
      await updateVehicle(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createVehicle(form)
      ElMessage.success('添加成功')
    }
    
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) {
      ElMessage.error(JSON.stringify(error.response.data))
    }
  } finally {
    saving.value = false
  }
}

const handleMaintenance = async (row) => {
  currentVehicle.value = row
  maintDialogVisible.value = true
  maintLoading.value = true
  try {
    const res = await getVehicleMaintenanceRecords(row.id)
    maintRecords.value = res.results || res.results || []
  } catch (error) {
    console.error(error)
    maintRecords.value = []
  } finally {
    maintLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这辆车吗？', '提示', { type: 'warning' })
    await deleteVehicle(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.vehicle-list {
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
</style>
