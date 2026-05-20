<template>
  <div class="bom-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>物料清单（BOM）</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加物料
          </el-button>
        </div>
      </template>

      <el-table :data="bomList" v-loading="loading" border>
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="specification" label="规格" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="planned_qty" label="计划数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.planned_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="actual_qty" label="实际数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.actual_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="estimated_cost" label="预估成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ toFixedSafe(row.estimated_cost) }}
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- BOM编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="resetForm"
    >
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="物料" prop="item">
          <el-select
            v-model="formData.item"
            placeholder="请选择物料"
            filterable
            remote
            :remote-method="searchItems"
            :loading="searchingItems"
            @change="handleItemChange"
            style="width: 100%"
          >
            <el-option
              v-for="item in itemOptions"
              :key="item.id"
              :label="`${item.sku} - ${item.name}`"
              :value="item.id"
            >
              <div style="display: flex; justify-content: space-between;">
                <span>{{ item.sku }} - {{ item.name }}</span>
                <span style="color: #8492a6; font-size: 13px">{{ item.specification }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="计划数量" prop="planned_qty">
          <el-input-number
            v-model="formData.planned_qty"
            :min="0"
            :step="1"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="实际数量" prop="actual_qty">
          <el-input-number
            v-model="formData.actual_qty"
            :min="0"
            :step="1"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="预估成本" prop="estimated_cost">
          <el-input-number
            v-model="formData.estimated_cost"
            :min="0"
            :step="0.01"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input
            v-model="formData.notes"
            type="textarea"
            :rows="3"
            placeholder="请输入备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { toFixedSafe } from '@/utils/number'

const props = defineProps({
  projectId: {
    type: [Number, String],
    required: true
  }
})

const emit = defineEmits(['refresh'])

const loading = ref(false)
const bomList = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const formRef = ref(null)
const submitting = ref(false)
const isEdit = ref(false)
const currentBomId = ref(null)

const itemOptions = ref([])
const searchingItems = ref(false)

const formData = ref({
  item: null,
  planned_qty: 0,
  actual_qty: 0,
  estimated_cost: 0,
  notes: ''
})

const rules = {
  item: [{ required: true, message: '请选择物料', trigger: 'change' }],
  planned_qty: [{ required: true, message: '请输入计划数量', trigger: 'blur' }]
}

const loadBOMList = async () => {
  loading.value = true
  try {
    const response = await request.get(`/projects/bom/`, {
      params: { project: props.projectId }
    })
    const data = response.data || response
    bomList.value = data.results || data
  } catch (error) {
    console.error('加载BOM失败:', error)
    ElMessage.error('加载BOM失败')
  } finally {
    loading.value = false
  }
}

const searchItems = async (query) => {
  if (!query) {
    itemOptions.value = []
    return
  }

  searchingItems.value = true
  try {
    const response = await request.get('/masterdata/items/', {
      params: { search: query, page_size: 20 }
    })
    const data = response.data || response
    itemOptions.value = data.results || data
  } catch (error) {
    console.error('搜索物料失败:', error)
  } finally {
    searchingItems.value = false
  }
}

const handleItemChange = (itemId) => {
  const selectedItem = itemOptions.value.find(item => item.id === itemId)
  if (selectedItem) {
    // 自动填充预估成本（使用标准成本）
    if (!formData.value.estimated_cost && selectedItem.standard_cost) {
      formData.value.estimated_cost = selectedItem.standard_cost * (formData.value.planned_qty || 1)
    }
  }
}

const handleAdd = async () => {
  isEdit.value = false
  dialogTitle.value = '添加物料'
  resetForm()
  // 预加载一些物料
  await searchItems('')
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  currentBomId.value = row.id
  dialogTitle.value = '编辑物料'
  formData.value = {
    item: row.item,
    planned_qty: row.planned_qty || 0,
    actual_qty: row.actual_qty || 0,
    estimated_cost: row.estimated_cost || 0,
    notes: row.notes || ''
  }
  // 将当前物料加入选项
  itemOptions.value = [{
    id: row.item,
    sku: row.item_sku,
    name: row.item_name,
    specification: row.specification
  }]
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该物料吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await request.delete(`/projects/bom/${row.id}/`)
    ElMessage.success('删除成功')
    loadBOMList()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除BOM失败:', error)
      ElMessage.error('删除BOM失败')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const payload = {
        ...formData.value,
        project: props.projectId
      }

      if (isEdit.value) {
        await request.put(`/projects/bom/${currentBomId.value}/`, payload)
        ElMessage.success('更新成功')
      } else {
        await request.post('/projects/bom/', payload)
        ElMessage.success('添加成功')
      }

      dialogVisible.value = false
      loadBOMList()
      emit('refresh')
    } catch (error) {
      console.error('保存BOM失败:', error)
      ElMessage.error(isEdit.value ? '更新BOM失败' : '添加BOM失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetForm = () => {
  formData.value = {
    item: null,
    planned_qty: 0,
    actual_qty: 0,
    estimated_cost: 0,
    notes: ''
  }
  currentBomId.value = null
  itemOptions.value = []
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

onMounted(() => {
  loadBOMList()
})

defineExpose({
  loadBOMList
})
</script>

<style scoped>
.bom-management {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
