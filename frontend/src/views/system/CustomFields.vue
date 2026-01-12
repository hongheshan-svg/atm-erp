<template>
  <div class="custom-fields-container">
    <div class="page-header">
      <h2>自定义字段配置</h2>
      <el-button type="primary" @click="showDialog = true">
        <el-icon><Plus /></el-icon>
        新增字段
      </el-button>
    </div>

    <!-- 模型选择 -->
    <el-card class="model-selector" shadow="never">
      <el-tabs v-model="selectedModel" @tab-change="loadFields">
        <el-tab-pane 
          v-for="model in supportedModels" 
          :key="model.value" 
          :label="model.label" 
          :name="model.value"
        />
      </el-tabs>
    </el-card>

    <!-- 字段列表 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ currentModelLabel }} - 自定义字段</span>
          <el-button size="small" @click="batchSort" v-if="fields.length">调整排序</el-button>
        </div>
      </template>

      <el-table :data="fields" v-loading="loading" stripe row-key="id">
        <el-table-column prop="field_code" label="字段编码" width="150">
          <template #default="{ row }">
            <code>{{ row.field_code }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="field_name" label="字段名称" min-width="150" />
        <el-table-column prop="field_type_display" label="字段类型" width="120" />
        <el-table-column prop="group_name" label="分组" width="120">
          <template #default="{ row }">
            <span>{{ row.group_name || '基本信息' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="80">
          <template #default="{ row }">
            <el-icon v-if="row.is_required" color="#67C23A"><Check /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="显示" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.is_visible" size="small" @change="toggleVisible(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="editField(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="deleteField(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && !fields.length" description="暂无自定义字段，点击上方按钮添加" />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog 
      v-model="showDialog" 
      :title="editing ? '编辑字段' : '新增字段'"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="字段编码" prop="field_code" required>
              <el-input v-model="form.field_code" :disabled="editing" placeholder="如：custom_size" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="字段名称" prop="field_name" required>
              <el-input v-model="form.field_name" placeholder="如：规格尺寸" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="字段类型" prop="field_type" required>
              <el-select v-model="form.field_type" style="width: 100%" @change="onFieldTypeChange">
                <el-option 
                  v-for="t in fieldTypes" 
                  :key="t.value" 
                  :label="t.label" 
                  :value="t.value" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分组">
              <el-input v-model="form.group_name" placeholder="可选，用于分组显示" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="必填">
              <el-switch v-model="form.is_required" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="可搜索">
              <el-switch v-model="form.is_searchable" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort_order" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 选项配置（下拉、单选、多选） -->
        <el-form-item v-if="needOptions" label="选项配置">
          <div class="options-editor">
            <div v-for="(opt, idx) in form.options" :key="idx" class="option-item">
              <el-input v-model="opt.value" placeholder="值" style="width: 120px" />
              <el-input v-model="opt.label" placeholder="显示文本" style="width: 180px" />
              <el-color-picker v-model="opt.color" size="small" />
              <el-button type="danger" circle size="small" @click="removeOption(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button size="small" @click="addOption">添加选项</el-button>
          </div>
        </el-form-item>

        <!-- 验证规则 -->
        <el-form-item label="验证规则">
          <el-row :gutter="10">
            <el-col :span="8" v-if="isNumberType">
              <el-input v-model.number="form.validation_rules.min" placeholder="最小值">
                <template #prepend>最小</template>
              </el-input>
            </el-col>
            <el-col :span="8" v-if="isNumberType">
              <el-input v-model.number="form.validation_rules.max" placeholder="最大值">
                <template #prepend>最大</template>
              </el-input>
            </el-col>
            <el-col :span="8" v-if="isTextType">
              <el-input v-model.number="form.validation_rules.maxLength" placeholder="最大长度">
                <template #prepend>最大长度</template>
              </el-input>
            </el-col>
          </el-row>
        </el-form-item>

        <el-form-item label="占位提示">
          <el-input v-model="form.placeholder" placeholder="输入框的占位文本" />
        </el-form-item>

        <el-form-item label="帮助文本">
          <el-input v-model="form.help_text" placeholder="字段的帮助说明" />
        </el-form-item>

        <el-form-item label="默认值">
          <el-input v-model="form.default_value" placeholder="可选" />
        </el-form-item>

        <el-form-item label="字段描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveField" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 排序对话框 -->
    <el-dialog v-model="showSortDialog" title="调整字段排序" width="500px">
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        拖动字段调整显示顺序
      </el-alert>
      <div class="sort-list">
        <div 
          v-for="(field, idx) in sortableFields" 
          :key="field.id" 
          class="sort-item"
          draggable="true"
          @dragstart="onDragStart($event, idx)"
          @dragover.prevent
          @drop="onDrop($event, idx)"
        >
          <el-icon><Rank /></el-icon>
          <span>{{ field.field_name }}</span>
          <code>{{ field.field_code }}</code>
        </div>
      </div>
      <template #footer>
        <el-button @click="showSortDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSortOrder" :loading="saving">保存排序</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Check, Rank } from '@element-plus/icons-vue'
import request from '@/utils/request'

const fields = ref([])
const loading = ref(false)
const saving = ref(false)
const showDialog = ref(false)
const showSortDialog = ref(false)
const editing = ref(null)
const selectedModel = ref('')
const supportedModels = ref([])
const fieldTypes = ref([])
const sortableFields = ref([])
const dragIndex = ref(null)

const form = ref({
  field_code: '',
  field_name: '',
  field_type: 'TEXT',
  group_name: '',
  is_required: false,
  is_searchable: true,
  is_visible: true,
  is_editable: true,
  sort_order: 0,
  placeholder: '',
  help_text: '',
  default_value: '',
  description: '',
  options: [],
  validation_rules: {}
})

const rules = {
  field_code: [{ required: true, message: '请输入字段编码', trigger: 'blur' }],
  field_name: [{ required: true, message: '请输入字段名称', trigger: 'blur' }],
  field_type: [{ required: true, message: '请选择字段类型', trigger: 'change' }]
}

const currentModelLabel = computed(() => {
  const model = supportedModels.value.find(m => m.value === selectedModel.value)
  return model?.label || ''
})

const needOptions = computed(() => {
  return ['SELECT', 'MULTISELECT', 'RADIO', 'CHECKBOX'].includes(form.value.field_type)
})

const isNumberType = computed(() => {
  return ['NUMBER', 'DECIMAL'].includes(form.value.field_type)
})

const isTextType = computed(() => {
  return ['TEXT', 'TEXTAREA'].includes(form.value.field_type)
})

const loadSupportedModels = async () => {
  try {
    const res = await request.get('/core/custom-field-definitions/supported_models/')
    supportedModels.value = res.data
    if (supportedModels.value.length) {
      selectedModel.value = supportedModels.value[0].value
      loadFields()
    }
  } catch (e) {
    console.error('加载模型列表失败:', e)
  }
}

const loadFieldTypes = async () => {
  try {
    const res = await request.get('/core/custom-field-definitions/field_types/')
    fieldTypes.value = res.data
  } catch (e) {
    console.error('加载字段类型失败:', e)
  }
}

const loadFields = async () => {
  if (!selectedModel.value) return
  loading.value = true
  try {
    const res = await request.get('/core/custom-field-definitions/', {
      params: { model_name: selectedModel.value }
    })
    fields.value = res.results || res || []
  } catch (e) {
    console.error('加载字段失败:', e)
  } finally {
    loading.value = false
  }
}

const editField = (field) => {
  editing.value = field
  form.value = { 
    ...field,
    validation_rules: field.validation_rules || {},
    options: field.options || []
  }
  showDialog.value = true
}

const onFieldTypeChange = () => {
  if (needOptions.value && !form.value.options?.length) {
    form.value.options = [{ value: '', label: '', color: '' }]
  }
}

const addOption = () => {
  if (!form.value.options) form.value.options = []
  form.value.options.push({ value: '', label: '', color: '' })
}

const removeOption = (idx) => {
  form.value.options.splice(idx, 1)
}

const saveField = async () => {
  saving.value = true
  try {
    const data = { ...form.value, model_name: selectedModel.value }
    if (editing.value) {
      await request.put(`/core/custom-field-definitions/${editing.value.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/core/custom-field-definitions/', data)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    editing.value = null
    resetForm()
    loadFields()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const resetForm = () => {
  form.value = {
    field_code: '',
    field_name: '',
    field_type: 'TEXT',
    group_name: '',
    is_required: false,
    is_searchable: true,
    is_visible: true,
    is_editable: true,
    sort_order: 0,
    placeholder: '',
    help_text: '',
    default_value: '',
    description: '',
    options: [],
    validation_rules: {}
  }
}

const toggleVisible = async (field) => {
  try {
    await request.post(`/core/custom-field-definitions/${field.id}/toggle_visible/`)
    ElMessage.success('操作成功')
  } catch (e) {
    field.is_visible = !field.is_visible
    ElMessage.error('操作失败')
  }
}

const deleteField = async (field) => {
  await ElMessageBox.confirm('确定要删除该字段吗？删除后该字段的所有数据将丢失', '确认删除', { type: 'warning' })
  try {
    await request.delete(`/core/custom-field-definitions/${field.id}/`)
    ElMessage.success('删除成功')
    loadFields()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const batchSort = () => {
  sortableFields.value = [...fields.value]
  showSortDialog.value = true
}

const onDragStart = (e, idx) => {
  dragIndex.value = idx
  e.dataTransfer.effectAllowed = 'move'
}

const onDrop = (e, idx) => {
  const dragItem = sortableFields.value[dragIndex.value]
  sortableFields.value.splice(dragIndex.value, 1)
  sortableFields.value.splice(idx, 0, dragItem)
  dragIndex.value = null
}

const saveSortOrder = async () => {
  saving.value = true
  try {
    const items = sortableFields.value.map((f, idx) => ({
      id: f.id,
      sort_order: idx
    }))
    await request.post('/core/custom-field-definitions/batch_sort/', { items })
    ElMessage.success('排序保存成功')
    showSortDialog.value = false
    loadFields()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSupportedModels()
  loadFieldTypes()
})
</script>

<style scoped lang="scss">
.custom-fields-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  
  h2 {
    margin: 0;
    color: #303133;
  }
}

.model-selector {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.options-editor {
  .option-item {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
}

.sort-list {
  .sort-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 6px;
    margin-bottom: 8px;
    cursor: grab;
    transition: all 0.3s;
    
    &:hover {
      background: #e6e8eb;
    }
    
    &:active {
      cursor: grabbing;
    }
    
    code {
      margin-left: auto;
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
