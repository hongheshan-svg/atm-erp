<template>
  <div class="contract-template-container">
    <div class="page-header">
      <h2>合同模板管理</h2>
      <div class="header-actions">
        <el-button type="primary" v-permission="'sales:contract:create'" @click="handleAddTemplate">
          <el-icon><Plus /></el-icon> 新增模板
        </el-button>
        <el-button @click="handleGenerateContract">生成合同</el-button>
      </div>
    </div>
    
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="合同模板" name="templates">
        <!-- 模板列表 -->
        <el-card shadow="never">
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="templates" v-loading="loading" border stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="code" label="模板编码" width="140" />
            <el-table-column prop="name" label="模板名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="contract_type_display" label="合同类型" width="120" />
            <el-table-column prop="format_display" label="格式" width="100" />
            <el-table-column prop="version" label="版本" width="80" />
            <el-table-column label="默认" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="success" size="small">是</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
                  {{ row.is_enabled ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handlePreview(row)">预览</el-button>
                <el-button type="primary" link size="small" v-permission="'sales:contract:edit'" @click="handleEditTemplate(row)">编辑</el-button>
                <el-button type="success" link size="small" @click="handleSetDefault(row)" v-if="!row.is_default">设为默认</el-button>
                <el-button type="danger" link size="small" v-permission="'sales:contract:delete'" @click="handleDeleteTemplate(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="条款库" name="clauses">
        <!-- 条款列表 -->
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>条款管理</span>
              <el-button type="primary" size="small" v-permission="'sales:contract:create'" @click="handleAddClause">新增条款</el-button>
            </div>
          </template>
          <el-table :data="clauses" v-loading="clauseLoading" border stripe>
            <el-table-column prop="code" label="条款编码" width="120" />
            <el-table-column prop="name" label="条款名称" width="180" />
            <el-table-column prop="clause_type_display" label="类型" width="100" />
            <el-table-column prop="content" label="条款内容" show-overflow-tooltip />
            <el-table-column label="必选" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_required" type="danger" size="small">是</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" v-permission="'sales:contract:edit'" @click="handleEditClause(row)">编辑</el-button>
                <el-button type="danger" link size="small" v-permission="'sales:contract:delete'" @click="handleDeleteClause(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="生成记录" name="generated">
        <!-- 生成的合同列表 -->
        <el-card shadow="never">
          <el-table :data="generatedContracts" v-loading="generatedLoading" border stripe>
            <el-table-column prop="contract_no" label="合同编号" width="140" />
            <el-table-column prop="contract_name" label="合同名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="contract_type_display" label="类型" width="100" />
            <el-table-column prop="party_a_name" label="甲方" width="150" show-overflow-tooltip />
            <el-table-column prop="party_b_name" label="乙方" width="150" show-overflow-tooltip />
            <el-table-column label="金额" width="120" align="right">
              <template #default="{ row }">
                ￥{{ formatAmount(row.total_amount) }}
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getStatusTag(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewContract(row)">查看</el-button>
                <el-button type="success" link size="small" @click="handlePrintContract(row)">打印</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
    
    <!-- 新增/编辑模板对话框 -->
    <el-dialog v-model="templateDialogVisible" :title="templateDialogTitle" width="800px" destroy-on-close>
      <el-form :model="templateForm" :rules="templateRules" ref="templateFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板编码" prop="code">
              <el-input v-model="templateForm.code" placeholder="请输入模板编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称" prop="name">
              <el-input v-model="templateForm.name" placeholder="请输入模板名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同类型" prop="contract_type">
              <el-select v-model="templateForm.contract_type" style="width: 100%">
                <el-option v-for="t in contractTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板格式">
              <el-select v-model="templateForm.format" style="width: 100%">
                <el-option label="HTML模板" value="HTML" />
                <el-option label="Word文档" value="WORD" />
                <el-option label="PDF模板" value="PDF" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="模板说明">
          <el-input v-model="templateForm.description" type="textarea" :rows="2" placeholder="请输入模板说明" />
        </el-form-item>
        <el-form-item label="付款条款">
          <div v-for="(term, index) in templateForm.payment_terms" :key="index" class="term-row">
            <el-input v-model="templateForm.payment_terms[index]" placeholder="请输入付款条款" />
            <el-button type="danger" :icon="Delete" circle size="small" @click="removePaymentTerm(index)" />
          </div>
          <el-button type="primary" link @click="addPaymentTerm">+ 添加付款条款</el-button>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="是否启用">
              <el-switch v-model="templateForm.is_enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设为默认">
              <el-switch v-model="templateForm.is_default" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitTemplate" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 生成合同对话框 -->
    <el-dialog v-model="generateDialogVisible" title="生成合同" width="800px" destroy-on-close>
      <el-form :model="contractForm" :rules="contractRules" ref="contractFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同编号" prop="contract_no">
              <el-input v-model="contractForm.contract_no" placeholder="请输入合同编号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同名称" prop="contract_name">
              <el-input v-model="contractForm.contract_name" placeholder="请输入合同名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同类型" prop="contract_type">
              <el-select v-model="contractForm.contract_type" style="width: 100%">
                <el-option v-for="t in contractTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同金额" prop="total_amount">
              <el-input-number v-model="contractForm.total_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">甲方信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="甲方名称" prop="party_a_name">
              <el-input v-model="contractForm.party_a_name" placeholder="请输入甲方名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="contractForm.party_a_contact" placeholder="请输入联系人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="contractForm.party_a_phone" placeholder="请输入电话" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="地址">
              <el-input v-model="contractForm.party_a_address" placeholder="请输入地址" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">乙方信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="乙方名称" prop="party_b_name">
              <el-input v-model="contractForm.party_b_name" placeholder="请输入乙方名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="contractForm.party_b_contact" placeholder="请输入联系人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="contractForm.party_b_phone" placeholder="请输入电话" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="地址">
              <el-input v-model="contractForm.party_b_address" placeholder="请输入地址" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitContract" :loading="generateLoading">生成合同</el-button>
      </template>
    </el-dialog>
    
    <!-- 预览对话框 -->
    <el-dialog v-model="previewDialogVisible" title="合同预览" width="900px" destroy-on-close>
      <div class="preview-container" v-html="previewContent"></div>
    </el-dialog>

    <!-- 条款编辑 -->
    <el-dialog v-model="clauseDialogVisible" :title="clauseIsEdit ? '编辑条款' : '添加条款'" width="600px">
      <el-form label-width="100px">
        <el-form-item label="条款标题">
          <el-input v-model="clauseForm.title" />
        </el-form-item>
        <el-form-item label="条款内容">
          <el-input v-model="clauseForm.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="clauseForm.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="是否必需">
          <el-switch v-model="clauseForm.is_required" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="clauseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="clauseSaving" @click="handleClauseSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { getContractTemplates, getContractClauses, getGeneratedContracts, getContractTypes, previewContractTemplate, setDefaultContractTemplate, deleteContractTemplate, updateContractTemplate, createContractTemplate, updateContractClause, createContractClause, deleteContractClause, generateContract, getGeneratedContract } from '@/api/sales'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/sales/')


const activeTab = ref('templates')
const loading = ref(false)
const clauseLoading = ref(false)
const clauseDialogVisible = ref(false)
const clauseIsEdit = ref(false)
const clauseSaving = ref(false)
// TODO: bind via UI when "管理条款 by template" is implemented; left as null for now
const currentTemplateId = ref(null)
const clauseForm = reactive({ id: null, title: '', content: '', sort_order: 0, is_required: true })
const generatedLoading = ref(false)
const submitLoading = ref(false)
const generateLoading = ref(false)

const templates = ref<any[]>([])
const clauses = ref<any[]>([])
const generatedContracts = ref<any[]>([])
const contractTypes = ref<any[]>([])

const templateDialogVisible = ref(false)
const templateDialogTitle = ref('新增模板')
const generateDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const previewContent = ref('')

const templateFormRef = ref(null)
const contractFormRef = ref(null)

const templateForm = reactive({
  code: '',
  name: '',
  contract_type: 'SALES',
  format: 'HTML',
  description: '',
  payment_terms: [],
  is_enabled: true,
  is_default: false
})

const templateRules = {
  code: [{ required: true, message: '请输入模板编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  contract_type: [{ required: true, message: '请选择合同类型', trigger: 'change' }]
}

const contractForm = reactive({
  contract_no: '',
  contract_name: '',
  contract_type: 'SALES',
  total_amount: 0,
  party_a_name: '',
  party_a_contact: '',
  party_a_phone: '',
  party_a_address: '',
  party_b_name: '深圳市奥特迈智能装备有限公司',
  party_b_contact: '',
  party_b_phone: '',
  party_b_address: ''
})

const contractRules = {
  contract_no: [{ required: true, message: '请输入合同编号', trigger: 'blur' }],
  contract_name: [{ required: true, message: '请输入合同名称', trigger: 'blur' }],
  party_a_name: [{ required: true, message: '请输入甲方名称', trigger: 'blur' }],
  party_b_name: [{ required: true, message: '请输入乙方名称', trigger: 'blur' }]
}

const fetchTemplates = async () => {
  loading.value = true
  try {
    const data = await getContractTemplates()
    templates.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchClauses = async () => {
  clauseLoading.value = true
  try {
    const data = await getContractClauses()
    clauses.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    clauseLoading.value = false
  }
}

const fetchGeneratedContracts = async () => {
  generatedLoading.value = true
  try {
    const data = await getGeneratedContracts()
    generatedContracts.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    generatedLoading.value = false
  }
}

const fetchContractTypes = async () => {
  try {
    const data = await getContractTypes()
    contractTypes.value = data
  } catch (e) {
    contractTypes.value = [
      { value: 'SALES', label: '销售合同' },
      { value: 'PURCHASE', label: '采购合同' },
      { value: 'SERVICE', label: '服务合同' },
      { value: 'NDA', label: '保密协议' },
      { value: 'FRAMEWORK', label: '框架协议' },
      { value: 'MAINTENANCE', label: '维保合同' }
    ]
  }
}

const handleTabChange = (tab) => {
  if (tab === 'templates') fetchTemplates()
  else if (tab === 'clauses') fetchClauses()
  else if (tab === 'generated') fetchGeneratedContracts()
}

const handleAddTemplate = () => {
  Object.assign(templateForm, {
    code: `CT-${Date.now().toString().slice(-6)}`,
    name: '',
    contract_type: 'SALES',
    format: 'HTML',
    description: '',
    payment_terms: [
      '合同签订后3个工作日内，甲方向乙方支付合同总额30%作为预付款',
      '设备发货前，甲方向乙方支付合同总额60%',
      '设备验收合格后7个工作日内，甲方向乙方支付合同总额10%作为质保金'
    ],
    is_enabled: true,
    is_default: false
  })
  templateDialogTitle.value = '新增模板'
  templateDialogVisible.value = true
}

const handleEditTemplate = (row) => {
  Object.assign(templateForm, row)
  templateDialogTitle.value = '编辑模板'
  templateDialogVisible.value = true
}

const handlePreview = async (row) => {
  try {
    const data = await previewContractTemplate(row.id)
    previewContent.value = data.html_content
    previewDialogVisible.value = true
  } catch (e) {
    ElMessage.error('预览失败')
  }
}

const handleSetDefault = async (row) => {
  try {
    await setDefaultContractTemplate(row.id)
    ElMessage.success('设置成功')
    fetchTemplates()
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

const handleDeleteTemplate = (row) => {
  ElMessageBox.confirm('确定要删除此模板吗？', '提示', { type: 'warning' })
    .then(async () => {
      await deleteContractTemplate(row.id)
      ElMessage.success('删除成功')
      fetchTemplates()
    })
}

const handleSubmitTemplate = async () => {
  const valid = await templateFormRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (templateForm.id) {
      await updateContractTemplate(templateForm.id, templateForm)
      ElMessage.success('修改成功')
    } else {
      await createContractTemplate(templateForm)
      ElMessage.success('创建成功')
    }
    templateDialogVisible.value = false
    fetchTemplates()
  } catch (e) {
    console.error(e)
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const addPaymentTerm = () => {
  templateForm.payment_terms.push('')
}

const removePaymentTerm = (index) => {
  templateForm.payment_terms.splice(index, 1)
}

const handleAddClause = () => {
  clauseIsEdit.value = false
  Object.assign(clauseForm, { id: null, title: '', content: '', sort_order: clauses.value.length + 1, is_required: true })
  clauseDialogVisible.value = true
}

const handleEditClause = (row) => {
  clauseIsEdit.value = true
  Object.assign(clauseForm, { id: row.id, title: row.title, content: row.content, sort_order: row.sort_order, is_required: row.is_required })
  clauseDialogVisible.value = true
}

const handleClauseSave = async () => {
  clauseSaving.value = true
  try {
    if (clauseIsEdit.value) {
      await updateContractClause(clauseForm.id, clauseForm)
      ElMessage.success('更新成功')
    } else {
      await createContractClause({ ...clauseForm, template: currentTemplateId.value })
      ElMessage.success('创建成功')
    }
    clauseDialogVisible.value = false
    fetchClauses()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
    else ElMessage.error('操作失败')
  } finally {
    clauseSaving.value = false
  }
}

const handleDeleteClause = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该条款吗？', '提示', { type: 'warning' })
    await deleteContractClause(row.id)
    ElMessage.success('删除成功')
    fetchClauses()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleGenerateContract = () => {
  Object.assign(contractForm, {
    contract_no: `HT-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`,
    contract_name: '',
    contract_type: 'SALES',
    total_amount: 0,
    party_a_name: '',
    party_a_contact: '',
    party_a_phone: '',
    party_a_address: '',
    party_b_name: '深圳市奥特迈智能装备有限公司',
    party_b_contact: '',
    party_b_phone: '',
    party_b_address: ''
  })
  generateDialogVisible.value = true
}

const handleSubmitContract = async () => {
  const valid = await contractFormRef.value?.validate()
  if (!valid) return
  
  generateLoading.value = true
  try {
    const data = await generateContract(contractForm)
    ElMessage.success('合同生成成功')
    generateDialogVisible.value = false
    
    // 显示预览
    previewContent.value = data.html_content
    previewDialogVisible.value = true
    
    fetchGeneratedContracts()
  } catch (e) {
    console.error(e)
    ElMessage.error('生成失败')
  } finally {
    generateLoading.value = false
  }
}

const handleViewContract = async (row) => {
  try {
    const data = await getGeneratedContract(row.id)
    previewContent.value = data.contract_content
    previewDialogVisible.value = true
  } catch (e) {
    ElMessage.error('获取合同失败')
  }
}

const handlePrintContract = (row) => {
  handleViewContract(row).then(() => {
    setTimeout(() => {
      window.print()
    }, 500)
  })
}

const formatAmount = (val) => {
  if (!val) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getStatusTag = (status) => {
  const tags = {
    DRAFT: 'info',
    PENDING: 'warning',
    APPROVED: 'primary',
    SIGNED: 'success',
    EFFECTIVE: 'success',
    EXPIRED: '',
    TERMINATED: 'danger'
  }
  return tags[status] || ''
}

onMounted(() => {
  fetchTemplates()
  fetchContractTypes()
})
</script>

<style scoped>
.contract-template-container {
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
  gap: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.term-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.term-row .el-input {
  flex: 1;
}

.preview-container {
  max-height: 70vh;
  overflow-y: auto;
  padding: 20px;
  background: #fff;
}

@media print {
  .preview-container {
    max-height: none;
  }
}
</style>
