<template>
  <div class="work-station-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工位管理</span>
          <el-button type="primary" v-permission="'production:process:create'" @click="handleCreate">新建工位</el-button>
        </div>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="code" label="工位编号" width="120" />
        <el-table-column prop="name" label="工位名称" />
        <el-table-column prop="work_center_name" label="所属工作中心" width="150" />
        <el-table-column prop="station_type_display" label="工位类型" width="120" />
        <el-table-column prop="capacity" label="产能" width="100" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'production:process:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" v-permission="'production:process:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑工位' : '新建工位'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工位名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="工位编号">
          <el-input v-model="form.code" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="工作中心">
          <el-select v-model="form.work_center" placeholder="选择工作中心" filterable style="width: 100%">
            <el-option v-for="wc in workCenters" :key="wc.id" :label="wc.name" :value="wc.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工位类型">
          <el-select v-model="form.station_type" style="width: 100%">
            <el-option label="装配" value="ASSEMBLY" />
            <el-option label="加工" value="MACHINING" />
            <el-option label="检测" value="INSPECTION" />
            <el-option label="包装" value="PACKING" />
          </el-select>
        </el-form-item>
        <el-form-item label="产能">
          <el-input-number v-model="form.capacity" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
getWorkStations, createWorkStation, updateWorkStation,
  deleteWorkStation as deleteWorkStationApi, getWorkCenters
} from '@/api/production'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/production/work-stations/')


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const workCenters = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, name: '', code: '', work_center: null, station_type: 'ASSEMBLY', capacity: 0, is_active: true })
const rules = { name: [{ required: true, message: '请输入工位名称', trigger: 'blur' }] }

const loadData = async () => {
  loading.value = true
  try {
    const res = await getWorkStations({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadWorkCenters = async () => {
  try {
    const res = await getWorkCenters({ page_size: 1000 })
    workCenters.value = res.results || res.results || []
  } catch (error) {
    console.error('WorkStationList getWorkCenters error:', error)
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', code: '', work_center: null, station_type: 'ASSEMBLY', capacity: 0, is_active: true })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, code: row.code, work_center: row.work_center, station_type: row.station_type, capacity: row.capacity, is_active: row.is_active })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateWorkStation(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createWorkStation(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该工位吗？', '提示', { type: 'warning' })
    await deleteWorkStationApi(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { loadWorkCenters(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
