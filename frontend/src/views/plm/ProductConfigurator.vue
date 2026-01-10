<template>
  <div class="configurator-container">
    <div class="page-header">
      <h2>产品配置器</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleNewTemplate">
          <el-icon><Plus /></el-icon>新建模板
        </el-button>
        <el-button @click="handleViewConfigs">配置记录</el-button>
      </div>
    </div>
    
    <el-row :gutter="16">
      <!-- 产品模板列表 -->
      <el-col :span="8">
        <el-card shadow="never" class="template-list-card">
          <template #header>
            <div class="card-header">
              <span>产品模板</span>
              <el-input v-model="searchQuery" placeholder="搜索模板..." 
                style="width: 160px" size="small" clearable @input="handleSearch">
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </div>
          </template>
          
          <div v-if="loading" class="loading-tip">加载中...</div>
          <div v-else-if="templateList.length === 0" class="empty-tip">暂无产品模板</div>
          <div v-else class="template-items">
            <div v-for="tpl in templateList" :key="tpl.id" 
              class="template-item" :class="{ active: selectedTemplate?.id === tpl.id }"
              @click="selectTemplate(tpl)">
              <div class="template-icon">
                <el-icon><Box /></el-icon>
              </div>
              <div class="template-info">
                <div class="template-name">{{ tpl.name }}</div>
                <div class="template-code">{{ tpl.code }}</div>
              </div>
              <div class="template-meta">
                <div class="template-price">¥{{ formatPrice(tpl.base_price) }}</div>
                <div class="template-params">{{ tpl.parameter_count }}个参数</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- 配置器区域 -->
      <el-col :span="16">
        <div v-if="!selectedTemplate" class="no-selection">
          <el-icon :size="64"><Setting /></el-icon>
          <p>请从左侧选择产品模板开始配置</p>
        </div>
        
        <template v-else>
          <el-card shadow="never" class="config-card">
            <template #header>
              <div class="config-header">
                <div class="config-title">
                  <h3>{{ selectedTemplate.name }}</h3>
                  <span class="config-version">版本 {{ selectedTemplate.version }}</span>
                </div>
                <el-button type="primary" @click="handleCreateConfig">
                  <el-icon><DocumentAdd /></el-icon>保存配置
                </el-button>
              </div>
            </template>
            
            <el-form label-width="140px" class="config-form">
              <template v-for="param in configParams" :key="param.id">
                <el-form-item 
                  :label="param.name" 
                  :required="param.is_required"
                  :class="{ 'affects-price': param.affects_price }">
                  
                  <!-- 选择型 -->
                  <template v-if="param.param_type === 'SELECT'">
                    <el-radio-group v-model="configValues[param.code]" @change="calculateResult">
                      <el-radio-button 
                        v-for="opt in param.options" 
                        :key="opt.id" 
                        :label="opt.value">
                        <span>{{ opt.label }}</span>
                        <span v-if="opt.price_adjustment > 0" class="price-tag">
                          +¥{{ formatPrice(opt.price_adjustment) }}
                        </span>
                      </el-radio-button>
                    </el-radio-group>
                  </template>
                  
                  <!-- 数值型 -->
                  <template v-else-if="param.param_type === 'NUMBER'">
                    <el-input-number 
                      v-model="configValues[param.code]"
                      :min="param.min_value"
                      :max="param.max_value"
                      :step="param.step || 1"
                      :precision="4"
                      @change="calculateResult"
                      style="width: 200px"
                    />
                    <span class="unit-label" v-if="param.unit">{{ param.unit }}</span>
                  </template>
                  
                  <!-- 文本型 -->
                  <template v-else-if="param.param_type === 'TEXT'">
                    <el-input 
                      v-model="configValues[param.code]"
                      :placeholder="param.help_text || '请输入'"
                      style="width: 300px"
                    />
                  </template>
                  
                  <!-- 开关型 -->
                  <template v-else-if="param.param_type === 'BOOL'">
                    <el-switch 
                      v-model="configValues[param.code]"
                      @change="calculateResult"
                    />
                  </template>
                  
                  <!-- 范围型 -->
                  <template v-else-if="param.param_type === 'RANGE'">
                    <el-slider
                      v-model="configValues[param.code]"
                      :min="param.min_value || 0"
                      :max="param.max_value || 100"
                      :step="param.step || 1"
                      show-input
                      @change="calculateResult"
                      style="width: 400px"
                    />
                  </template>
                  
                  <div v-if="param.description" class="param-desc">{{ param.description }}</div>
                </el-form-item>
              </template>
            </el-form>
          </el-card>
          
          <!-- 配置结果 -->
          <el-card shadow="never" class="result-card" style="margin-top: 16px">
            <template #header>配置结果</template>
            
            <el-row :gutter="32">
              <el-col :span="8">
                <div class="result-item price">
                  <div class="result-label">总价格</div>
                  <div class="result-value">¥{{ formatPrice(calcResult.total_price) }}</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="result-item lead-time">
                  <div class="result-label">交货期</div>
                  <div class="result-value">{{ calcResult.lead_time || 0 }}天</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="result-item bom-count">
                  <div class="result-label">BOM物料</div>
                  <div class="result-value">{{ (calcResult.bom_items || []).length }}项</div>
                </div>
              </el-col>
            </el-row>
            
            <!-- 生成的BOM清单 -->
            <div v-if="calcResult.bom_items?.length" class="bom-list">
              <h4>BOM清单</h4>
              <el-table :data="calcResult.bom_items" size="small" border stripe>
                <el-table-column prop="item_code" label="物料编码" width="140" />
                <el-table-column prop="item_name" label="物料名称" min-width="180" />
                <el-table-column prop="quantity" label="数量" width="100" align="right" />
                <el-table-column prop="source" label="来源" min-width="150" show-overflow-tooltip />
              </el-table>
            </div>
          </el-card>
        </template>
      </el-col>
    </el-row>
    
    <!-- 新建模板对话框 -->
    <el-dialog v-model="templateDialogVisible" title="新建产品模板" width="700px">
      <el-form :model="templateForm" :rules="templateRules" ref="templateFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板编码" prop="code">
              <el-input v-model="templateForm.code" placeholder="唯一编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称" prop="name">
              <el-input v-model="templateForm.name" placeholder="模板名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="基础价格">
              <el-input-number v-model="templateForm.base_price" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="基础工期">
              <el-input-number v-model="templateForm.base_lead_time" :min="0" style="width: 100%">
                <template #suffix>天</template>
              </el-input-number>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="模板描述">
          <el-input v-model="templateForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTemplate" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 保存配置对话框 -->
    <el-dialog v-model="saveConfigDialogVisible" title="保存产品配置" width="500px">
      <el-form :model="saveConfigForm" label-width="80px">
        <el-form-item label="配置名称" required>
          <el-input v-model="saveConfigForm.name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="saveConfigForm.customer" placeholder="选择客户(可选)" 
            style="width: 100%" clearable filterable>
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="saveConfigForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitConfig" :loading="submitLoading">保存配置</el-button>
      </template>
    </el-dialog>
    
    <!-- 配置记录对话框 -->
    <el-dialog v-model="configListDialogVisible" title="配置记录" width="1000px">
      <el-table :data="configList" v-loading="configLoading" border stripe>
        <el-table-column prop="config_no" label="配置编号" width="130" />
        <el-table-column prop="name" label="配置名称" min-width="180" />
        <el-table-column prop="template_name" label="产品模板" width="150" />
        <el-table-column prop="customer_name" label="客户" width="120" />
        <el-table-column prop="total_price" label="总价格" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.total_price) }}
          </template>
        </el-table-column>
        <el-table-column prop="lead_time" label="交期" width="80" align="center">
          <template #default="{ row }">
            {{ row.lead_time }}天
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleLoadConfig(row)">加载</el-button>
            <el-button type="success" link size="small" @click="handleConfirmConfig(row)" 
              v-if="row.status === 'DRAFT'">确认</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
    
    <!-- 参数管理对话框 -->
    <el-dialog v-model="paramDialogVisible" :title="`管理参数 - ${selectedTemplate?.name}`" width="900px">
      <el-button type="primary" size="small" @click="handleAddParam" style="margin-bottom: 16px">
        添加参数
      </el-button>
      
      <el-table :data="templateParams" size="small" border stripe>
        <el-table-column prop="sort_order" label="排序" width="60" align="center" />
        <el-table-column prop="name" label="参数名称" width="140" />
        <el-table-column prop="code" label="参数编码" width="120" />
        <el-table-column prop="param_type_display" label="类型" width="100" />
        <el-table-column prop="default_value" label="默认值" width="100" />
        <el-table-column label="选项" width="80" align="center">
          <template #default="{ row }">
            {{ row.options?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="is_required" label="必填" width="60" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_required" color="#67c23a"><Check /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="affects_price" label="影响价格" width="80" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.affects_price" color="#e6a23c"><Coin /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEditParam(row)">编辑</el-button>
            <el-button type="primary" link size="small" @click="handleManageOptions(row)" 
              v-if="row.param_type === 'SELECT'">选项</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Box, Setting, DocumentAdd, Check, Coin } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitLoading = ref(false)
const configLoading = ref(false)
const searchQuery = ref('')

const templateList = ref([])
const selectedTemplate = ref(null)
const configParams = ref([])
const configValues = reactive({})
const calcResult = ref({
  total_price: 0,
  lead_time: 0,
  bom_items: []
})

const customers = ref([])
const configList = ref([])

// 新建模板
const templateDialogVisible = ref(false)
const templateFormRef = ref(null)
const templateForm = reactive({
  code: '',
  name: '',
  base_price: 0,
  base_lead_time: 30,
  description: ''
})
const templateRules = {
  code: [{ required: true, message: '请输入模板编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }]
}

// 保存配置
const saveConfigDialogVisible = ref(false)
const saveConfigForm = reactive({
  name: '',
  customer: null,
  notes: ''
})

// 配置列表
const configListDialogVisible = ref(false)

// 参数管理
const paramDialogVisible = ref(false)
const templateParams = ref([])

const fetchTemplates = async () => {
  loading.value = true
  try {
    const params = { search: searchQuery.value, is_active: true }
    const { data } = await request.get('/projects/product-templates/', { params })
    templateList.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    const { data } = await request.get('/masterdata/customers/')
    customers.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const handleSearch = () => {
  fetchTemplates()
}

const selectTemplate = async (template) => {
  selectedTemplate.value = template
  
  try {
    const { data } = await request.get(`/projects/product-templates/${template.id}/configurator/`)
    configParams.value = data.parameters || []
    
    // 初始化配置值为默认值
    Object.keys(configValues).forEach(key => delete configValues[key])
    configParams.value.forEach(param => {
      if (param.default_value) {
        configValues[param.code] = param.default_value
      } else if (param.param_type === 'SELECT') {
        const defaultOpt = param.options?.find(o => o.is_default)
        if (defaultOpt) {
          configValues[param.code] = defaultOpt.value
        }
      } else if (param.param_type === 'NUMBER') {
        configValues[param.code] = param.min_value || 0
      } else if (param.param_type === 'BOOL') {
        configValues[param.code] = false
      }
    })
    
    // 初始计算
    calculateResult()
  } catch (e) {
    ElMessage.error('加载模板失败')
  }
}

const calculateResult = async () => {
  if (!selectedTemplate.value) return
  
  try {
    const { data } = await request.post(
      `/projects/product-templates/${selectedTemplate.value.id}/calculate/`,
      { config_values: configValues }
    )
    calcResult.value = data
  } catch (e) {
    console.error(e)
  }
}

const handleNewTemplate = () => {
  Object.assign(templateForm, {
    code: '',
    name: '',
    base_price: 0,
    base_lead_time: 30,
    description: ''
  })
  templateDialogVisible.value = true
}

const submitTemplate = async () => {
  const valid = await templateFormRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await request.post('/projects/product-templates/', templateForm)
    ElMessage.success('模板创建成功')
    templateDialogVisible.value = false
    fetchTemplates()
  } catch (e) {
    ElMessage.error(e.response?.data?.code?.[0] || '创建失败')
  } finally {
    submitLoading.value = false
  }
}

const handleCreateConfig = () => {
  saveConfigForm.name = `${selectedTemplate.value.name} - 配置`
  saveConfigForm.customer = null
  saveConfigForm.notes = ''
  saveConfigDialogVisible.value = true
}

const submitConfig = async () => {
  if (!saveConfigForm.name) {
    ElMessage.warning('请输入配置名称')
    return
  }
  
  submitLoading.value = true
  try {
    await request.post('/projects/product-configurations/', {
      template: selectedTemplate.value.id,
      name: saveConfigForm.name,
      customer: saveConfigForm.customer,
      config_values: configValues,
      notes: saveConfigForm.notes
    })
    ElMessage.success('配置已保存')
    saveConfigDialogVisible.value = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const handleViewConfigs = async () => {
  configLoading.value = true
  configListDialogVisible.value = true
  
  try {
    const { data } = await request.get('/projects/product-configurations/')
    configList.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    configLoading.value = false
  }
}

const handleLoadConfig = async (config) => {
  // 加载配置到当前编辑器
  const template = templateList.value.find(t => t.id === config.template)
  if (template) {
    await selectTemplate(template)
    Object.assign(configValues, config.config_values)
    calculateResult()
    configListDialogVisible.value = false
    ElMessage.success('配置已加载')
  }
}

const handleConfirmConfig = async (config) => {
  try {
    await request.post(`/projects/product-configurations/${config.id}/confirm/`)
    ElMessage.success('配置已确认')
    handleViewConfigs()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    CONFIRMED: 'success',
    ORDERED: 'primary',
    CANCELLED: 'danger'
  }
  return types[status] || ''
}

const formatPrice = (price) => {
  if (!price) return '0.00'
  return Number(price).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatDateTime = (datetime) => {
  if (!datetime) return ''
  return new Date(datetime).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchTemplates()
  fetchCustomers()
})
</script>

<style scoped>
.configurator-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.template-list-card {
  height: calc(100vh - 200px);
  overflow: hidden;
}

.template-list-card :deep(.el-card__body) {
  height: calc(100% - 60px);
  overflow-y: auto;
  padding: 0;
}

.loading-tip, .empty-tip {
  text-align: center;
  padding: 40px 0;
  color: #909399;
}

.template-items {
  padding: 8px;
}

.template-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 8px;
  border: 1px solid #ebeef5;
}

.template-item:hover {
  background: #f5f7fa;
}

.template-item.active {
  background: #ecf5ff;
  border-color: #409eff;
}

.template-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  margin-right: 12px;
}

.template-info {
  flex: 1;
}

.template-name {
  font-weight: 500;
  color: #303133;
}

.template-code {
  font-size: 12px;
  color: #909399;
}

.template-meta {
  text-align: right;
}

.template-price {
  font-size: 14px;
  font-weight: 500;
  color: #f56c6c;
}

.template-params {
  font-size: 12px;
  color: #909399;
}

.no-selection {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #c0c4cc;
}

.no-selection p {
  margin-top: 16px;
  font-size: 14px;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-title h3 {
  margin: 0;
  display: inline;
  font-size: 16px;
}

.config-version {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}

.config-form {
  padding: 16px 0;
}

.config-form :deep(.el-form-item) {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.config-form :deep(.el-form-item.affects-price .el-form-item__label) {
  position: relative;
}

.config-form :deep(.el-form-item.affects-price .el-form-item__label::after) {
  content: '¥';
  position: absolute;
  right: 10px;
  color: #e6a23c;
  font-size: 12px;
}

.price-tag {
  font-size: 11px;
  color: #f56c6c;
  margin-left: 4px;
}

.unit-label {
  margin-left: 8px;
  color: #909399;
}

.param-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.result-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
}

.result-item {
  text-align: center;
  padding: 20px;
}

.result-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.result-value {
  font-size: 28px;
  font-weight: bold;
}

.result-item.price .result-value {
  color: #f56c6c;
}

.result-item.lead-time .result-value {
  color: #409eff;
}

.result-item.bom-count .result-value {
  color: #67c23a;
}

.bom-list {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #dcdfe6;
}

.bom-list h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #606266;
}
</style>
