<template>
  <div class="equipment-capability-matrix">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="设备总数" :value="stats.totalEquipment" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="已标定能力" :value="stats.calibrated" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="工艺覆盖率" :value="stats.processCoverage" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="平均OEE" :value="stats.avgOEE" suffix="%" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 能力矩阵 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>设备-工艺能力矩阵</span>
          <div>
            <el-button @click="loadMatrix">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button type="primary" @click="dialogVisible = true">
              <el-icon><Plus /></el-icon>新增能力标定
            </el-button>
          </div>
        </div>
      </template>

      <!-- 按工艺查询 -->
      <div style="margin-bottom: 16px;">
        <el-select v-model="selectedProcess" placeholder="按工艺筛选" clearable style="width: 200px; margin-right: 12px" @change="loadMatrix">
          <el-option v-for="p in processTypes" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-select v-model="selectedGrade" placeholder="精度等级" clearable style="width: 150px" @change="loadMatrix">
          <el-option label="标准" value="standard" />
          <el-option label="精密" value="precision" />
          <el-option label="高精密" value="high_precision" />
          <el-option label="超精密" value="ultra_precision" />
        </el-select>
      </div>

      <el-table :data="capabilityList" v-loading="loading" stripe>
        <el-table-column prop="equipment_name" label="设备" min-width="150" fixed />
        <el-table-column prop="process_type_display" label="工艺类型" width="120" />
        <el-table-column prop="precision_grade_display" label="精度等级" width="100">
          <template #default="{ row }">
            <el-tag :type="gradeType(row.precision_grade)">{{ row.precision_grade_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="加工范围" width="200">
          <template #default="{ row }">
            {{ row.max_length || '-' }} × {{ row.max_width || '-' }} × {{ row.max_height || '-' }} mm
          </template>
        </el-table-column>
        <el-table-column prop="max_weight" label="最大重量(kg)" width="120" align="right" />
        <el-table-column prop="positioning_accuracy" label="定位精度(mm)" width="120" align="right" />
        <el-table-column prop="repeat_accuracy" label="重复精度(mm)" width="120" align="right" />
        <el-table-column label="效率系数" width="100" align="center">
          <template #default="{ row }">
            <el-progress :percentage="(row.efficiency_factor || 0) * 100" :show-text="false" :stroke-width="8" />
            <span style="font-size: 12px;">{{ ((row.efficiency_factor || 0) * 100).toFixed(0) }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size"
          :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @change="loadList" />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑能力标定' : '新增能力标定'" width="650px">
      <el-form :model="form" ref="formRef" label-width="110px" :rules="formRules">
        <el-form-item label="设备" prop="equipment">
          <el-input v-model="form.equipment" placeholder="设备ID" />
        </el-form-item>
        <el-form-item label="工艺类型" prop="process_type">
          <el-select v-model="form.process_type" style="width: 100%">
            <el-option v-for="p in processTypes" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="精度等级" prop="precision_grade">
          <el-select v-model="form.precision_grade" style="width: 100%">
            <el-option label="标准" value="standard" />
            <el-option label="精密" value="precision" />
            <el-option label="高精密" value="high_precision" />
            <el-option label="超精密" value="ultra_precision" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="最大长度"><el-input-number v-model="form.max_length" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="最大宽度"><el-input-number v-model="form.max_width" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="最大高度"><el-input-number v-model="form.max_height" :min="0" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="最大重量"><el-input-number v-model="form.max_weight" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="定位精度"><el-input-number v-model="form.positioning_accuracy" :min="0" :step="0.001" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="重复精度"><el-input-number v-model="form.repeat_accuracy" :min="0" :step="0.001" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="效率系数">
          <el-slider v-model="form.efficiency_factor_pct" :min="0" :max="100" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  getEquipmentCapabilities, createEquipmentCapability,
  updateEquipmentCapability, deleteEquipmentCapability,
  getCapabilityMatrix
} from '@/api/production'

const loading = ref(false)
const submitLoading = ref(false)
const capabilityList = ref([])
const total = ref(0)
const dialogVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)
const selectedProcess = ref('')
const selectedGrade = ref('')

const stats = reactive({ totalEquipment: 0, calibrated: 0, processCoverage: 0, avgOEE: 0 })
const queryParams = reactive({ page: 1, page_size: 20 })

const processTypes = [
  { value: 'milling', label: '铣削' }, { value: 'turning', label: '车削' },
  { value: 'grinding', label: '磨削' }, { value: 'drilling', label: '钻孔' },
  { value: 'boring', label: '镗削' }, { value: 'edm', label: '电火花' },
  { value: 'wire_cutting', label: '线切割' }, { value: 'laser_cutting', label: '激光切割' },
  { value: 'welding', label: '焊接' }, { value: 'bending', label: '折弯' },
  { value: 'stamping', label: '冲压' }, { value: 'casting', label: '铸造' },
  { value: 'forging', label: '锻造' }, { value: 'heat_treatment', label: '热处理' },
  { value: 'surface_treatment', label: '表面处理' }, { value: 'assembly', label: '装配' }
]

const form = reactive({
  equipment: '', process_type: '', precision_grade: 'standard',
  max_length: null, max_width: null, max_height: null, max_weight: null,
  positioning_accuracy: null, repeat_accuracy: null, efficiency_factor_pct: 85
})
const formRules = {
  equipment: [{ required: true, message: '请选择设备' }],
  process_type: [{ required: true, message: '请选择工艺类型' }],
  precision_grade: [{ required: true, message: '请选择精度等级' }]
}

const gradeType = (g) => ({ standard: 'info', precision: '', high_precision: 'warning', ultra_precision: 'danger' }[g] || 'info')

const loadList = async () => {
  loading.value = true
  try {
    const params = { ...queryParams }
    if (selectedProcess.value) params.process_type = selectedProcess.value
    if (selectedGrade.value) params.precision_grade = selectedGrade.value
    const res = await getEquipmentCapabilities(params)
    capabilityList.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
    stats.calibrated = total.value
  } finally {
    loading.value = false
  }
}

const loadMatrix = () => { loadList() }

const handleEdit = (row) => {
  editId.value = row.id
  Object.assign(form, { ...row, efficiency_factor_pct: (row.efficiency_factor || 0.85) * 100 })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    const data = { ...form, efficiency_factor: form.efficiency_factor_pct / 100 }
    delete data.efficiency_factor_pct
    if (editId.value) {
      await updateEquipmentCapability(editId.value, data)
    } else {
      await createEquipmentCapability(data)
    }
    ElMessage.success(editId.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    editId.value = null
    loadList()
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确认删除该能力标定？', '提示')
  await deleteEquipmentCapability(row.id)
  ElMessage.success('删除成功')
  loadList()
}

onMounted(() => { loadList() })
</script>

<style scoped>
.equipment-capability-matrix { padding: 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
