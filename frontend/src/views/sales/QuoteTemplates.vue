<template>
  <div class="quote-templates-container">
    <div class="page-header">
      <h2>报价单模板管理</h2>
      <el-button type="primary" @click="showTemplateDialog = true">
        <el-icon><Plus /></el-icon>
        新增模板
      </el-button>
    </div>

    <el-row :gutter="20">
      <!-- 左侧模板列表 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <span>模板列表</span>
          </template>
          <el-scrollbar height="calc(100vh - 280px)">
            <div 
              v-for="tpl in templates" 
              :key="tpl.id" 
              class="template-card"
              :class="{ active: selectedTemplate?.id === tpl.id }"
              @click="selectTemplate(tpl)"
            >
              <div class="template-icon">
                <el-icon :size="32">
                  <Document v-if="tpl.format === 'EXCEL'" />
                  <Document v-else-if="tpl.format === 'PDF'" />
                  <Monitor v-else />
                </el-icon>
              </div>
              <div class="template-info">
                <div class="template-name">{{ tpl.name }}</div>
                <div class="template-meta">
                  <el-tag size="small">{{ tpl.format_display }}</el-tag>
                  <el-tag v-if="tpl.is_default" type="success" size="small">默认</el-tag>
                  <el-tag v-if="!tpl.is_enabled" type="info" size="small">禁用</el-tag>
                </div>
              </div>
            </div>
            <el-empty v-if="!templates.length" description="暂无模板" />
          </el-scrollbar>
        </el-card>
      </el-col>

      <!-- 右侧详情/生成 -->
      <el-col :span="16">
        <el-card v-if="selectedTemplate" shadow="never">
          <template #header>
            <div class="card-header">
              <span>{{ selectedTemplate.name }}</span>
              <div class="actions">
                <el-button size="small" @click="editTemplate">编辑</el-button>
                <el-button size="small" type="primary" @click="setDefault" :disabled="selectedTemplate.is_default">
                  设为默认
                </el-button>
                <el-button size="small" type="success" @click="showGenerateDialog = true">
                  生成报价单
                </el-button>
              </div>
            </div>
          </template>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="模板编码">{{ selectedTemplate.code }}</el-descriptions-item>
            <el-descriptions-item label="模板格式">{{ selectedTemplate.format_display }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="selectedTemplate.is_enabled ? 'success' : 'info'">
                {{ selectedTemplate.is_enabled ? '启用' : '禁用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="默认模板">
              <el-tag v-if="selectedTemplate.is_default" type="success">是</el-tag>
              <span v-else>否</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">表头配置</el-divider>
          <pre class="config-preview">{{ JSON.stringify(selectedTemplate.header_config, null, 2) }}</pre>

          <el-divider content-position="left">列配置</el-divider>
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="selectedTemplate.column_config || []" size="small" stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="key" label="字段" width="100" />
            <el-table-column prop="label" label="标题" />
            <el-table-column prop="width" label="宽度" width="80" />
          </el-table>

          <el-divider content-position="left">表尾配置</el-divider>
          <pre class="config-preview">{{ JSON.stringify(selectedTemplate.footer_config, null, 2) }}</pre>
        </el-card>

        <el-card v-else shadow="never">
          <el-empty description="请从左侧选择模板" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 生成报价单对话框 -->
    <el-dialog v-model="showGenerateDialog" title="生成报价单" width="900px" :close-on-click-modal="false">
      <el-form :model="quoteForm" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="报价单号" required>
              <el-input v-model="quoteForm.quote_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户名称" required>
              <el-input v-model="quoteForm.customer_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目名称">
              <el-input v-model="quoteForm.project_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="有效期至">
              <el-date-picker v-model="quoteForm.valid_until" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="quoteForm.contact_person" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="quoteForm.contact_phone" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>报价明细</el-divider>
        <el-table :data="quoteForm.items" border>
          <el-table-column label="名称" min-width="150">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="规格型号" width="120">
            <template #default="{ row }">
              <el-input v-model="row.spec" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="80">
            <template #default="{ row }">
              <el-input v-model="row.unit" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="数量" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.quantity" size="small" :min="0" controls-position="right" @change="calcAmount(row)" />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.unit_price" size="small" :min="0" :precision="2" controls-position="right" @change="calcAmount(row)" />
            </template>
          </el-table-column>
          <el-table-column label="金额" width="120">
            <template #default="{ row }">
              <span style="font-weight: bold;">¥{{ toFixedSafe(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="120">
            <template #default="{ row }">
              <el-input v-model="row.remark" size="small" />
            </template>
          </el-table-column>
          <el-table-column width="60">
            <template #default="{ $index }">
              <el-button type="danger" size="small" circle @click="removeItem($index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button @click="addItem" style="margin-top: 10px">添加明细行</el-button>

        <div class="total-row">
          <span>合计金额：</span>
          <span class="total-amount">¥{{ totalAmount.toFixed(2) }}</span>
        </div>

        <el-form-item label="备注">
          <el-input v-model="quoteForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" @click="generateQuote" :loading="generating">生成报价单</el-button>
      </template>
    </el-dialog>

    <!-- 模板编辑对话框 -->
    <el-dialog v-model="showTemplateDialog" :title="editingTemplate ? '编辑模板' : '新增模板'" width="700px">
      <el-form :model="templateForm" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板编码" required>
              <el-input v-model="templateForm.code" :disabled="editingTemplate" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称" required>
              <el-input v-model="templateForm.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板格式">
              <el-select v-model="templateForm.format" style="width: 100%">
                <el-option label="Excel模板" value="EXCEL" />
                <el-option label="PDF模板" value="PDF" />
                <el-option label="HTML模板" value="HTML" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态">
              <el-switch v-model="templateForm.is_enabled" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="表头配置">
          <el-input 
            v-model="templateForm.header_config_json" 
            type="textarea" 
            :rows="4" 
            placeholder='{"company_name": "公司名称"}'
          />
        </el-form-item>
        <el-form-item label="表尾配置">
          <el-input 
            v-model="templateForm.footer_config_json" 
            type="textarea" 
            :rows="4" 
            placeholder='{"terms": ["条款1", "条款2"]}'
          />
        </el-form-item>
        <el-form-item label="模板说明">
          <el-input v-model="templateForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTemplateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Document, Monitor, Delete } from '@element-plus/icons-vue'
import { toFixedSafe } from '@/utils/number'
import { getQuoteTemplates, createQuoteTemplate, updateQuoteTemplate, setDefaultQuoteTemplate, generateQuoteFromTemplate } from '@/api/sales'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/sales/')


const templates = ref<any[]>([])
const selectedTemplate = ref(null)
const showTemplateDialog = ref(false)
const showGenerateDialog = ref(false)
const editingTemplate = ref(null)
const saving = ref(false)
const generating = ref(false)

const templateForm = ref({
  code: '',
  name: '',
  format: 'EXCEL',
  is_enabled: true,
  header_config_json: '{}',
  footer_config_json: '{}',
  description: ''
})

const quoteForm = ref({
  quote_no: '',
  customer_name: '',
  project_name: '',
  valid_until: null,
  contact_person: '',
  contact_phone: '',
  remarks: '',
  items: [{ name: '', spec: '', unit: '套', quantity: 1, unit_price: 0, amount: 0, remark: '' }]
})

const totalAmount = computed(() => {
  return quoteForm.value.items.reduce((sum, item) => sum + (item.amount || 0), 0)
})

const loadTemplates = async () => {
  try {
    const res = await getQuoteTemplates()
    templates.value = res.results || res || []
  } catch (e) {
    console.error('加载模板失败:', e)
  }
}

const selectTemplate = (tpl) => {
  selectedTemplate.value = tpl
}

const editTemplate = () => {
  editingTemplate.value = selectedTemplate.value
  templateForm.value = {
    ...selectedTemplate.value,
    header_config_json: JSON.stringify(selectedTemplate.value.header_config || {}, null, 2),
    footer_config_json: JSON.stringify(selectedTemplate.value.footer_config || {}, null, 2)
  }
  showTemplateDialog.value = true
}

const saveTemplate = async () => {
  saving.value = true
  try {
    let headerConfig = {}
    let footerConfig = {}
    try {
      headerConfig = JSON.parse(templateForm.value.header_config_json || '{}')
      footerConfig = JSON.parse(templateForm.value.footer_config_json || '{}')
    } catch (e) {
      ElMessage.error('JSON格式错误')
      saving.value = false
      return
    }
    
    const data = {
      ...templateForm.value,
      header_config: headerConfig,
      footer_config: footerConfig
    }
    delete data.header_config_json
    delete data.footer_config_json
    
    if (editingTemplate.value) {
      await updateQuoteTemplate(editingTemplate.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createQuoteTemplate(data)
      ElMessage.success('创建成功')
    }
    showTemplateDialog.value = false
    editingTemplate.value = null
    loadTemplates()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const setDefault = async () => {
  try {
    await setDefaultQuoteTemplate(selectedTemplate.value.id)
    ElMessage.success('设置成功')
    loadTemplates()
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

const addItem = () => {
  quoteForm.value.items.push({
    name: '',
    spec: '',
    unit: '套',
    quantity: 1,
    unit_price: 0,
    amount: 0,
    remark: ''
  })
}

const removeItem = (idx) => {
  quoteForm.value.items.splice(idx, 1)
}

const calcAmount = (row) => {
  row.amount = (row.quantity || 0) * (row.unit_price || 0)
}

const generateQuote = async () => {
  if (!quoteForm.value.quote_no || !quoteForm.value.customer_name) {
    ElMessage.warning('请填写报价单号和客户名称')
    return
  }
  
  generating.value = true
  try {
    const res = await generateQuoteFromTemplate({
      template_id: selectedTemplate.value?.id,
      ...quoteForm.value,
      output_format: 'excel'
    })
    
    if (res.success) {
      ElMessage.success('报价单生成成功')
      // 下载文件
      if (res.download_url) {
        window.open(res.download_url, '_blank')
      }
      showGenerateDialog.value = false
    }
  } catch (e) {
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  loadTemplates()
  // 生成默认报价单号
  quoteForm.value.quote_no = `QT-${new Date().getFullYear()}-${String(Date.now()).slice(-6)}`
})
</script>

<style scoped lang="scss">
.quote-templates-container {
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

.template-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.3s;
  
  &:hover {
    background: #f5f7fa;
    border-color: #c0c4cc;
  }
  
  &.active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-color: transparent;
    color: white;
    
    .template-meta :deep(.el-tag) {
      background: rgba(255, 255, 255, 0.2);
      color: white;
      border-color: transparent;
    }
  }
  
  .template-icon {
    width: 50px;
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f0f0f0;
    border-radius: 8px;
  }
  
  &.active .template-icon {
    background: rgba(255, 255, 255, 0.2);
  }
  
  .template-info {
    flex: 1;
  }
  
  .template-name {
    font-weight: 500;
    margin-bottom: 8px;
  }
  
  .template-meta {
    display: flex;
    gap: 8px;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-preview {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  overflow: auto;
  max-height: 150px;
}

.total-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin: 20px 0;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .total-amount {
    font-size: 24px;
    font-weight: bold;
    color: #f56c6c;
  }
}
</style>
