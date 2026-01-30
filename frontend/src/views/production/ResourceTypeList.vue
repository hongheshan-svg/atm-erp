<template>
  <div class="resource-type-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>资源类型管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>新建类型
          </el-button>
        </div>
      </template>

      <el-table :data="resourceTypes" v-loading="loading" stripe>
        <el-table-column prop="code" label="类型编码" width="120" />
        <el-table-column prop="name" label="类型名称" width="150" />
        <el-table-column label="类别" width="120">
          <template #default="{ row }">
            <el-tag :type="getCategoryType(row.category)">{{ row.category_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="resource_count" label="资源数量" width="100" align="center">
          <template #default="{ row }">
            {{ row.resource_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="editType(row)">编辑</el-button>
            <el-button size="small" link :type="row.is_active ? 'warning' : 'success'"
                       @click="toggleActive(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="isEdit ? '编辑资源类型' : '新建资源类型'" width="500px">
      <el-form :model="typeForm" :rules="typeRules" ref="typeFormRef" label-width="100px">
        <el-form-item label="类型编码" prop="code">
          <el-input v-model="typeForm.code" :disabled="isEdit" placeholder="例如: MACHINE" />
        </el-form-item>
        <el-form-item label="类型名称" prop="name">
          <el-input v-model="typeForm.name" placeholder="例如: 机加工设备" />
        </el-form-item>
        <el-form-item label="类别" prop="category">
          <el-select v-model="typeForm.category" style="width: 100%">
            <el-option label="工位" value="WORKSTATION" />
            <el-option label="设备" value="EQUIPMENT" />
            <el-option label="人员" value="PERSONNEL" />
            <el-option label="工装夹具" value="TOOL" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="typeForm.description" type="textarea" :rows="2" placeholder="资源类型描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveType" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const isEdit = ref(false)

const resourceTypes = ref([])
const editingId = ref(null)

const typeForm = reactive({
  code: '',
  name: '',
  category: 'WORKSTATION',
  description: ''
})

const typeRules = {
  code: [{ required: true, message: '请输入类型编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入类型名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择类别', trigger: 'change' }]
}

const typeFormRef = ref(null)

const formatMoney = (val) => Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })

const getCategoryType = (category) => {
  const map = {
    WORKSTATION: 'warning',
    EQUIPMENT: 'primary',
    PERSONNEL: 'success',
    TOOL: 'info'
  }
  return map[category] || 'info'
}

const loadResourceTypes = async () => {
  loading.value = true
  try {
    const res = await request.get('/production/resource-types/')
    resourceTypes.value = res.results || res
  } catch (e) {
    ElMessage.error('加载资源类型失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  typeForm.code = ''
  typeForm.name = ''
  typeForm.category = 'MACHINE'
  typeForm.description = ''
  typeForm.default_efficiency = 1.0
  typeForm.default_cost_rate = 100
  typeForm.capabilities = []
}

const editType = (row) => {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(typeForm, {
    code: row.code,
    name: row.name,
    category: row.category,
    description: row.description,
    default_efficiency: row.default_efficiency,
    default_cost_rate: row.default_cost_rate,
    capabilities: row.capabilities || []
  })
  showCreateDialog.value = true
}

const saveType = async () => {
  try {
    await typeFormRef.value.validate()
    submitting.value = true
    
    if (isEdit.value) {
      await request.put(`/api/production/resource-types/${editingId.value}/`, typeForm)
      ElMessage.success('资源类型已更新')
    } else {
      await request.post('/production/resource-types/', typeForm)
      ElMessage.success('资源类型已创建')
    }
    
    showCreateDialog.value = false
    loadResourceTypes()
  } catch (e) {
    if (e !== false) ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const toggleActive = async (row) => {
  try {
    await request.patch(`/api/production/resource-types/${row.id}/`, { is_active: !row.is_active })
    ElMessage.success('状态已更新')
    loadResourceTypes()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// 监听对话框关闭
const closeDialog = () => {
  isEdit.value = false
  editingId.value = null
  resetForm()
}

onMounted(() => {
  loadResourceTypes()
})
</script>

<style scoped>
.resource-type-list {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
