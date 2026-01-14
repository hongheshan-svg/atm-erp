<template>
  <div class="vehicle-request-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用车申请</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建申请
          </el-button>
        </div>
      </template>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="用途">
          <el-select v-model="searchForm.purpose" placeholder="选择用途" clearable style="width: 120px;">
            <el-option label="商务出行" value="BUSINESS" />
            <el-option label="客户拜访" value="VISIT" />
            <el-option label="送货" value="DELIVERY" />
            <el-option label="接送" value="PICKUP" />
            <el-option label="外出开会" value="MEETING" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待审批" value="PENDING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="使用中" value="IN_USE" />
            <el-option label="已归还" value="RETURNED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column prop="request_no" label="申请单号" width="130" />
        <el-table-column prop="vehicle_plate" label="车辆" width="100" />
        <el-table-column prop="purpose_display" label="用途" width="100" />
        <el-table-column prop="departure" label="出发地" width="120" show-overflow-tooltip />
        <el-table-column prop="destination" label="目的地" width="120" show-overflow-tooltip />
        <el-table-column label="用车时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="申请时间" width="160" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'DRAFT'" size="small" type="primary" @click="handleSubmit(row)">提交</el-button>
            <el-button v-if="row.status === 'APPROVED'" size="small" type="success" @click="handlePickup(row)">取车</el-button>
            <el-button v-if="row.status === 'IN_USE'" size="small" type="warning" @click="handleReturn(row)">还车</el-button>
            <el-button v-if="row.status === 'DRAFT'" size="small" type="danger" @click="handleDelete(row)">删除</el-button>
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
    <el-dialog v-model="dialogVisible" title="用车申请" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="申请车辆" prop="vehicle">
              <el-select v-model="form.vehicle" placeholder="选择车辆" style="width: 100%;">
                <el-option 
                  v-for="v in availableVehicles" 
                  :key="v.id" 
                  :label="`${v.plate_number} (${v.brand} ${v.model})`" 
                  :value="v.id" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用途" prop="purpose">
              <el-select v-model="form.purpose" style="width: 100%;">
                <el-option label="商务出行" value="BUSINESS" />
                <el-option label="客户拜访" value="VISIT" />
                <el-option label="送货" value="DELIVERY" />
                <el-option label="接送" value="PICKUP" />
                <el-option label="外出开会" value="MEETING" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker v-model="form.start_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计结束" prop="end_time">
              <el-date-picker v-model="form.end_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="出发地" prop="departure">
              <el-input v-model="form.departure" placeholder="如：公司" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目的地" prop="destination">
              <el-input v-model="form.destination" placeholder="如：客户公司" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="乘客人数">
          <el-input-number v-model="form.passengers" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="详细说明" prop="purpose_detail">
          <el-input v-model="form.purpose_detail" type="textarea" :rows="3" placeholder="请详细说明用车原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 还车对话框 -->
    <el-dialog v-model="returnDialogVisible" title="还车登记" width="500px" destroy-on-close>
      <el-form :model="returnForm" label-width="100px">
        <el-form-item label="归还里程">
          <el-input-number v-model="returnForm.end_mileage" :min="0" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="油费">
          <el-input-number v-model="returnForm.fuel_cost" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="过路费">
          <el-input-number v-model="returnForm.toll_cost" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="停车费">
          <el-input-number v-model="returnForm.parking_cost" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="returnDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmReturn" :loading="saving">确认还车</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const availableVehicles = ref([])
const dialogVisible = ref(false)
const returnDialogVisible = ref(false)
const currentItem = ref(null)
const formRef = ref(null)

const searchForm = reactive({
  purpose: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  vehicle: null,
  purpose: 'BUSINESS',
  start_time: '',
  end_time: '',
  departure: '',
  destination: '',
  passengers: 1,
  purpose_detail: ''
})

const returnForm = reactive({
  end_mileage: 0,
  fuel_cost: 0,
  toll_cost: 0,
  parking_cost: 0
})

const rules = {
  purpose: [{ required: true, message: '请选择用途', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
  departure: [{ required: true, message: '请输入出发地', trigger: 'blur' }],
  destination: [{ required: true, message: '请输入目的地', trigger: 'blur' }],
  purpose_detail: [{ required: true, message: '请输入详细说明', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'IN_USE': 'primary',
    'RETURNED': '',
    'CANCELLED': 'info'
  }
  return types[status] || 'info'
}

const formatDateTime = (datetime) => {
  if (!datetime) return ''
  return new Date(datetime).toLocaleString('zh-CN', { 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

const loadVehicles = async () => {
  try {
    const res = await request.get('/oa/vehicles/available/')
    // res 已经是 response.data
    availableVehicles.value = Array.isArray(res) ? res : (res.results || [])
  } catch (error) {
    console.error('加载车辆失败', error)
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
    const res = await request.get('/oa/vehicle-requests/', { params })
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
  Object.assign(form, {
    vehicle: null,
    purpose: 'BUSINESS',
    start_time: '',
    end_time: '',
    departure: '',
    destination: '',
    passengers: 1,
    purpose_detail: ''
  })
  loadVehicles()
  dialogVisible.value = true
}

const handleView = (row) => {
  ElMessage.info('查看详情功能开发中')
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    
    await request.post('/oa/vehicle-requests/', form)
    ElMessage.success('申请已保存')
    
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

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交这个用车申请吗？', '提示', { type: 'warning' })
    await request.post(`/oa/vehicle-requests/${row.id}/submit/`)
    ElMessage.success('提交成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败')
    }
  }
}

const handlePickup = async (row) => {
  try {
    await ElMessageBox.confirm('确认取车？', '提示', { type: 'info' })
    await request.post(`/oa/vehicle-requests/${row.id}/pickup/`)
    ElMessage.success('取车成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const handleReturn = (row) => {
  currentItem.value = row
  Object.assign(returnForm, {
    end_mileage: row.start_mileage || 0,
    fuel_cost: 0,
    toll_cost: 0,
    parking_cost: 0
  })
  returnDialogVisible.value = true
}

const confirmReturn = async () => {
  saving.value = true
  try {
    await request.post(`/oa/vehicle-requests/${currentItem.value.id}/return_vehicle/`, returnForm)
    ElMessage.success('还车成功')
    returnDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这个用车申请吗？', '提示', { type: 'warning' })
    await request.delete(`/oa/vehicle-requests/${row.id}/`)
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
.vehicle-request-list {
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
