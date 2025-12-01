<template>
  <div class="dashboard-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>仪表盘组件配置</span>
          <el-button type="primary" @click="showForm = true">
            <el-icon><Plus /></el-icon>
            新增组件
          </el-button>
        </div>
      </template>

      <!-- Table -->
      <el-table :data="widgets" v-loading="loading" stripe>
        <el-table-column prop="name" label="组件名称" width="150" />
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column prop="widget_type_display" label="类型" width="100" />
        <el-table-column prop="data_source_display" label="数据源" width="120" />
        <el-table-column prop="default_width" label="宽度" width="80" />
        <el-table-column prop="default_height" label="高度" width="80" />
        <el-table-column prop="refresh_interval" label="刷新间隔" width="100">
          <template #default="{ row }">{{ row.refresh_interval }}秒</template>
        </el-table-column>
        <el-table-column prop="is_active" label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_system" label="系统组件" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" type="warning">系统</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="previewWidget(row)">预览</el-button>
            <el-button size="small" type="primary" @click="editWidget(row)" :disabled="row.is_system">
              编辑
            </el-button>
            <el-button size="small" type="danger" @click="deleteWidget(row)" :disabled="row.is_system">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Form Dialog -->
    <el-dialog v-model="showForm" :title="editingId ? '编辑组件' : '新增组件'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="组件名称" prop="name">
          <el-input v-model="form.name" placeholder="组件名称" />
        </el-form-item>
        <el-form-item label="组件编码" prop="code">
          <el-input v-model="form.code" placeholder="唯一编码" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="组件类型" prop="widget_type">
          <el-select v-model="form.widget_type" placeholder="选择类型">
            <el-option
              v-for="type in widgetTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数据源" prop="data_source">
          <el-select v-model="form.data_source" placeholder="选择数据源">
            <el-option
              v-for="source in dataSources"
              :key="source.value"
              :label="source.label"
              :value="source.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="默认宽度">
          <el-slider v-model="form.default_width" :min="1" :max="12" show-input />
        </el-form-item>
        <el-form-item label="默认高度">
          <el-input-number v-model="form.default_height" :min="100" :max="600" :step="50" /> px
        </el-form-item>
        <el-form-item label="刷新间隔">
          <el-input-number v-model="form.refresh_interval" :min="60" :max="3600" :step="60" /> 秒
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="自定义SQL" v-if="form.data_source === 'custom_sql'">
          <el-input v-model="form.custom_query" type="textarea" :rows="4" placeholder="SELECT ..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- Preview Dialog -->
    <el-dialog v-model="showPreview" :title="`预览: ${previewData?.name}`" width="800px">
      <div v-loading="previewLoading" class="preview-container">
        <pre>{{ JSON.stringify(previewData?.data, null, 2) }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import * as dashboardApi from '@/api/dashboard'

const loading = ref(false)
const submitting = ref(false)
const showForm = ref(false)
const showPreview = ref(false)
const previewLoading = ref(false)
const widgets = ref([])
const widgetTypes = ref([])
const dataSources = ref([])
const editingId = ref(null)
const formRef = ref(null)
const previewData = ref(null)

const form = reactive({
  name: '',
  code: '',
  widget_type: '',
  data_source: '',
  default_width: 6,
  default_height: 200,
  refresh_interval: 300,
  is_active: true,
  custom_query: '',
  config: {}
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  widget_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  data_source: [{ required: true, message: '请选择数据源', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await dashboardApi.getWidgets()
    widgets.value = res.results || res
  } finally {
    loading.value = false
  }
}

const fetchOptions = async () => {
  const [types, sources] = await Promise.all([
    dashboardApi.getWidgetTypes(),
    dashboardApi.getDataSources()
  ])
  widgetTypes.value = types
  dataSources.value = sources
}

const previewWidget = async (row) => {
  previewData.value = { name: row.name, data: null }
  showPreview.value = true
  previewLoading.value = true
  try {
    const data = await dashboardApi.getWidgetData(row.id)
    previewData.value.data = data
  } finally {
    previewLoading.value = false
  }
}

const editWidget = (row) => {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    code: row.code,
    widget_type: row.widget_type,
    data_source: row.data_source,
    default_width: row.default_width,
    default_height: row.default_height,
    refresh_interval: row.refresh_interval,
    is_active: row.is_active,
    custom_query: row.custom_query || '',
    config: row.config || {}
  })
  showForm.value = true
}

const deleteWidget = async (row) => {
  await ElMessageBox.confirm('确定删除此组件?', '确认')
  await dashboardApi.deleteWidget(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

const submitForm = async () => {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (editingId.value) {
      await dashboardApi.updateWidget(editingId.value, form)
    } else {
      await dashboardApi.createWidget(form)
    }
    ElMessage.success('保存成功')
    showForm.value = false
    resetForm()
    fetchData()
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  Object.assign(form, {
    name: '',
    code: '',
    widget_type: '',
    data_source: '',
    default_width: 6,
    default_height: 200,
    refresh_interval: 300,
    is_active: true,
    custom_query: '',
    config: {}
  })
}

onMounted(() => {
  fetchData()
  fetchOptions()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.preview-container {
  max-height: 400px;
  overflow: auto;
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
}
.preview-container pre {
  margin: 0;
  white-space: pre-wrap;
}
</style>
