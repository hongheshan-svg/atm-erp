<template>
  <div class="email-templates-container">
    <div class="page-header">
      <h2>邮件模板管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showDialog = true">
          <el-icon><Plus /></el-icon>
          新增模板
        </el-button>
        <el-button @click="initSystemTemplates" :loading="initLoading">
          初始化系统模板
        </el-button>
      </div>
    </div>

    <!-- 搜索过滤 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true">
        <el-form-item label="模板类型">
          <el-select v-model="filters.template_type" placeholder="全部类型" clearable>
            <el-option 
              v-for="t in templateTypes" 
              :key="t.value" 
              :label="t.label" 
              :value="t.value" 
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.is_enabled" placeholder="全部" clearable>
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.search" placeholder="搜索模板" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTemplates">搜索</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 模板列表 -->
    <el-card shadow="never">
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="templates" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="code" label="模板编码" width="180" />
        <el-table-column prop="name" label="模板名称" min-width="200" />
        <el-table-column prop="template_type_display" label="类型" width="120" />
        <el-table-column prop="subject" label="邮件主题" min-width="250" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'danger'" size="small">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="系统模板" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" type="info" size="small">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="previewTemplate(row)">预览</el-button>
            <el-button size="small" text type="primary" @click="editTemplate(row)">编辑</el-button>
            <el-button size="small" text type="success" @click="testSend(row)">测试发送</el-button>
            <el-button 
              size="small" 
              text 
              :type="row.is_enabled ? 'warning' : 'success'" 
              @click="toggleTemplate(row)"
            >
              {{ row.is_enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button 
              size="small" 
              text 
              type="danger" 
              @click="deleteTemplate(row)"
              :disabled="row.is_system"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @change="loadTemplates"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog 
      v-model="showDialog" 
      :title="editing ? '编辑邮件模板' : '新增邮件模板'"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板编码" required>
              <el-input v-model="form.code" :disabled="editing" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板类型" required>
              <el-select v-model="form.template_type" style="width: 100%">
                <el-option 
                  v-for="t in templateTypes" 
                  :key="t.value" 
                  :label="t.label" 
                  :value="t.value" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态">
              <el-switch v-model="form.is_enabled" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="邮件主题" required>
          <el-input v-model="form.subject" placeholder="支持变量，如：{{ title }}" />
        </el-form-item>
        <el-form-item label="HTML内容" required>
          <el-input 
            v-model="form.body_html" 
            type="textarea" 
            :rows="15" 
            placeholder="HTML格式邮件内容，支持Django模板变量"
          />
        </el-form-item>
        <el-form-item label="纯文本内容">
          <el-input 
            v-model="form.body_text" 
            type="textarea" 
            :rows="5" 
            placeholder="可选，用于不支持HTML的邮件客户端"
          />
        </el-form-item>
        <el-form-item label="可用变量">
          <el-input 
            v-model="variablesInput" 
            placeholder="变量列表，逗号分隔，如：recipient_name, title, link"
          />
        </el-form-item>
        <el-form-item label="模板说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreview" title="模板预览" width="800px">
      <div class="preview-section">
        <h4>邮件主题</h4>
        <p>{{ previewData.subject }}</p>
      </div>
      <div class="preview-section">
        <h4>邮件内容</h4>
        <div class="html-preview" v-html="previewData.html_body"></div>
      </div>
      <div class="preview-section" v-if="previewData.variables_used?.length">
        <h4>使用的变量</h4>
        <el-tag v-for="v in previewData.variables_used" :key="v" size="small" style="margin-right: 8px;">
          {{ v }}
        </el-tag>
      </div>
    </el-dialog>

    <!-- 测试发送对话框 -->
    <el-dialog v-model="showTestDialog" title="测试发送" width="500px">
      <el-form :model="testForm" label-width="100px">
        <el-form-item label="收件人邮箱" required>
          <el-input v-model="testForm.email" placeholder="请输入测试邮箱" />
        </el-form-item>
        <el-form-item label="测试数据">
          <el-input 
            v-model="testForm.contextJson" 
            type="textarea" 
            :rows="8" 
            placeholder='JSON格式，如：{"recipient_name": "张三", "title": "测试标题"}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTestDialog = false">取消</el-button>
        <el-button type="primary" @click="doTestSend" :loading="sending">发送测试</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getEmailTemplateList, getEmailTemplateTypes, createEmailTemplate, updateEmailTemplate, deleteEmailTemplate, toggleEmailTemplate, previewEmailTemplate, testSendEmailTemplate, initSystemEmailTemplates } from '@/api/system'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/core/email-templates/')


const templates = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const sending = ref(false)
const initLoading = ref(false)
const showDialog = ref(false)
const showPreview = ref(false)
const showTestDialog = ref(false)
const editing = ref(null)
const templateTypes = ref<any[]>([])

const filters = ref({
  template_type: '',
  is_enabled: null,
  search: ''
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = ref({
  code: '',
  name: '',
  template_type: 'CUSTOM',
  subject: '',
  body_html: '',
  body_text: '',
  variables: [],
  description: '',
  is_enabled: true
})

const variablesInput = computed({
  get: () => form.value.variables?.join(', ') || '',
  set: (val) => {
    form.value.variables = val.split(',').map(v => v.trim()).filter(v => v)
  }
})

const previewData = ref({
  subject: '',
  html_body: '',
  variables_used: []
})

const testForm = ref({
  email: '',
  contextJson: '{}'
})

const testingTemplate = ref(null)

const loadTemplateTypes = async () => {
  try {
    const res = await getEmailTemplateTypes()
    templateTypes.value = res
  } catch (e) {
    console.error('加载模板类型失败:', e)
  }
}

const loadTemplates = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      ...filters.value
    }
    const res = await getEmailTemplateList(params)
    templates.value = res.results || res || []
    pagination.value.total = res.count || templates.value.length
  } catch (e) {
    console.error('加载模板失败:', e)
  } finally {
    loading.value = false
  }
}

const editTemplate = (template) => {
  editing.value = template
  form.value = { ...template }
  showDialog.value = true
}

const saveTemplate = async () => {
  saving.value = true
  try {
    if (editing.value) {
      await updateEmailTemplate(editing.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createEmailTemplate(form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    editing.value = null
    resetForm()
    loadTemplates()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const resetForm = () => {
  form.value = {
    code: '',
    name: '',
    template_type: 'CUSTOM',
    subject: '',
    body_html: '',
    body_text: '',
    variables: [],
    description: '',
    is_enabled: true
  }
}

const toggleTemplate = async (template) => {
  try {
    await toggleEmailTemplate(template.id)
    ElMessage.success('操作成功')
    loadTemplates()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const deleteTemplate = async (template) => {
  if (template.is_system) {
    ElMessage.warning('系统模板不能删除')
    return
  }
  await ElMessageBox.confirm('确定要删除该模板吗？', '确认删除', { type: 'warning' })
  try {
    await deleteEmailTemplate(template.id)
    ElMessage.success('删除成功')
    loadTemplates()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const previewTemplate = async (template) => {
  try {
    const res = await previewEmailTemplate(template.id, {
      context: {
        recipient_name: '张三',
        title: '测试标题',
        approval_type: '采购审批',
        applicant: '李四',
        apply_time: '2025-01-09 10:00:00',
        link: 'https://example.com/approval/1'
      }
    })
    previewData.value = res
    showPreview.value = true
  } catch (e) {
    ElMessage.error('预览失败')
  }
}

const testSend = (template) => {
  testingTemplate.value = template
  testForm.value = {
    email: '',
    contextJson: JSON.stringify({
      recipient_name: '测试用户',
      title: '测试邮件',
      link: 'https://example.com'
    }, null, 2)
  }
  showTestDialog.value = true
}

const doTestSend = async () => {
  if (!testForm.value.email) {
    ElMessage.warning('请输入收件人邮箱')
    return
  }
  
  let context = {}
  try {
    context = JSON.parse(testForm.value.contextJson)
  } catch (e) {
    ElMessage.error('测试数据格式错误，请输入有效的JSON')
    return
  }
  
  sending.value = true
  try {
    const res = await testSendEmailTemplate(testingTemplate.value.id, {
      email: testForm.value.email,
      context
    })
    if (res.status === 'SENT') {
      ElMessage.success('测试邮件发送成功')
      showTestDialog.value = false
    } else {
      ElMessage.error(res.message || '发送失败')
    }
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    sending.value = false
  }
}

const initSystemTemplates = async () => {
  initLoading.value = true
  try {
    const res = await initSystemEmailTemplates()
    ElMessage.success(res.message || '初始化成功')
    loadTemplates()
  } catch (e) {
    ElMessage.error('初始化失败')
  } finally {
    initLoading.value = false
  }
}

onMounted(() => {
  loadTemplateTypes()
  loadTemplates()
})
</script>

<style scoped lang="scss">
.email-templates-container {
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

.filter-card {
  margin-bottom: 20px;
  
  :deep(.el-card__body) {
    padding-bottom: 2px;
  }
}

.preview-section {
  margin-bottom: 20px;
  
  h4 {
    margin: 0 0 10px 0;
    color: #606266;
    border-left: 3px solid #409eff;
    padding-left: 10px;
  }
  
  p {
    padding: 10px;
    background: #f5f7fa;
    border-radius: 4px;
  }
}

.html-preview {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 20px;
  max-height: 400px;
  overflow: auto;
  background: white;
}
</style>
