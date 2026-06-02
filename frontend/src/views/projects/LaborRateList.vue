<template>
  <div class="labor-rate-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工时费率标准</span>
          <el-button type="primary" v-permission="'projects:project:create'" @click="handleCreate">新增费率</el-button>
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
        <el-table-column prop="work_type_display" label="工种" width="150" />
        <el-table-column prop="standard_rate" label="标准费率" align="right">
          <template #default="{ row }">¥ {{ row.standard_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="overtime_rate" label="加班费率" align="right">
          <template #default="{ row }">¥ {{ row.overtime_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="weekend_rate" label="周末费率" align="right">
          <template #default="{ row }">¥ {{ row.weekend_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="holiday_rate" label="节假日费率" align="right">
          <template #default="{ row }">¥ {{ row.holiday_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="effective_from" label="生效日期" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑费率' : '新增费率'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工种" prop="work_type">
          <el-select v-model="form.work_type" placeholder="选择工种" style="width: 100%">
            <el-option label="电气工程师" value="ELECTRICAL" />
            <el-option label="机械工程师" value="MECHANICAL" />
            <el-option label="PLC工程师" value="PLC" />
            <el-option label="装配技工" value="ASSEMBLER" />
            <el-option label="焊工" value="WELDER" />
            <el-option label="普工" value="GENERAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准费率" prop="standard_rate">
          <el-input-number v-model="form.standard_rate" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="加班费率" prop="overtime_rate">
          <el-input-number v-model="form.overtime_rate" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="周末费率">
          <el-input-number v-model="form.weekend_rate" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="节假日费率">
          <el-input-number v-model="form.holiday_rate" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日期" prop="effective_from">
          <el-date-picker v-model="form.effective_from" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
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
import { ElMessage } from 'element-plus'
import { getLaborRateList, createLaborRate, updateLaborRate } from '@/api/projects/labor-rate'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_labor-rate/')


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, work_type: '', standard_rate: 0, overtime_rate: 0, weekend_rate: 0, holiday_rate: 0, effective_from: '' })

const rules = {
  work_type: [{ required: true, message: '请选择工种', trigger: 'change' }],
  standard_rate: [{ required: true, message: '请输入标准费率', trigger: 'blur' }],
  effective_from: [{ required: true, message: '请选择生效日期', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getLaborRateList()
    tableData.value = res.results || res.results || res || []
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, work_type: '', standard_rate: 0, overtime_rate: 0, weekend_rate: 0, holiday_rate: 0, effective_from: '' })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, work_type: row.work_type, standard_rate: row.standard_rate, overtime_rate: row.overtime_rate, weekend_rate: row.weekend_rate, holiday_rate: row.holiday_rate, effective_from: row.effective_from })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateLaborRate(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createLaborRate(form)
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

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
