<template>
  <div class="quote-estimation">
    <el-card class="filter-card">
      <div class="filter-header">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon> 新建估算
        </el-button>
        <div class="filter-right">
          <el-input v-model="searchText" placeholder="搜索估算单" clearable style="width: 200px" @clear="loadData" @keyup.enter="loadData">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px; margin-left: 10px" @change="loadData">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="评审中" value="REVIEW" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已报价" value="QUOTED" />
          </el-select>
        </div>
      </div>
    </el-card>

    <el-card class="data-card">
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="estimation_no" label="估算单号" width="140" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="project_type" label="项目类型" width="120" />
        <el-table-column label="总成本" width="120" align="right">
          <template #default="{ row }">
            <span class="money">¥{{ formatMoney(row.total_cost) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="建议报价" width="120" align="right">
          <template #default="{ row }">
            <span class="money primary">¥{{ formatMoney(row.suggested_price) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="目标利润率" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.target_profit_rate >= 20 ? 'success' : 'warning'">
              {{ row.target_profit_rate }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总工期" width="90" align="center">
          <template #default="{ row }">{{ row.total_days }}天</template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button type="primary" link @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-dropdown trigger="click" @command="cmd => handleCommand(cmd, row)">
              <el-button type="primary" link>更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="calculate">重新计算</el-dropdown-item>
                  <el-dropdown-item command="import_bom">从BOM导入</el-dropdown-item>
                  <el-dropdown-item command="import_history">参考历史项目</el-dropdown-item>
                  <el-dropdown-item command="submit" v-if="row.status === 'DRAFT'">提交评审</el-dropdown-item>
                  <el-dropdown-item command="approve" v-if="row.status === 'REVIEW'">审批通过</el-dropdown-item>
                  <el-dropdown-item command="create_quote" v-if="row.status === 'APPROVED'">生成报价单</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入项目名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="form.customer" filterable placeholder="选择客户" style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目类型">
              <el-select v-model="form.project_type" placeholder="选择类型" style="width: 100%">
                <el-option label="自动化产线" value="自动化产线" />
                <el-option label="自动化设备" value="自动化设备" />
                <el-option label="检测设备" value="检测设备" />
                <el-option label="夹具工装" value="夹具工装" />
                <el-option label="改造升级" value="改造升级" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联商机">
              <el-select v-model="form.opportunity" filterable clearable placeholder="选择商机" style="width: 100%">
                <el-option v-for="o in opportunities" :key="o.id" :label="o.name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="项目描述">
          <el-input v-model="form.project_description" type="textarea" :rows="3" placeholder="请描述项目概况" />
        </el-form-item>
        <el-form-item label="技术要求">
          <el-input v-model="form.technical_requirements" type="textarea" :rows="3" placeholder="请输入技术要求" />
        </el-form-item>
        <el-divider content-position="left">费率设置</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="管理费率">
              <el-input-number v-model="form.management_rate" :min="0" :max="50" :precision="2" style="width: 100%">
                <template #suffix>%</template>
              </el-input-number>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风险预备率">
              <el-input-number v-model="form.risk_rate" :min="0" :max="30" :precision="2" style="width: 100%">
                <template #suffix>%</template>
              </el-input-number>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标利润率">
              <el-input-number v-model="form.target_profit_rate" :min="0" :max="50" :precision="2" style="width: 100%">
                <template #suffix>%</template>
              </el-input-number>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const searchText = ref('')
const statusFilter = ref('')

const dialogVisible = ref(false)
const dialogTitle = ref('新建报价估算')
const submitting = ref(false)
const formRef = ref(null)
const customers = ref([])
const opportunities = ref([])

const form = reactive({
  name: '',
  customer: null,
  opportunity: null,
  project_type: '',
  project_description: '',
  technical_requirements: '',
  management_rate: 10,
  risk_rate: 5,
  target_profit_rate: 20
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }]
}

const formatMoney = (val) => {
  if (!val) return '0.00'
  return parseFloat(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getStatusType = (status) => {
  const map = {
    DRAFT: 'info',
    REVIEW: 'warning',
    APPROVED: 'success',
    QUOTED: 'primary',
    WON: 'success',
    LOST: 'danger'
  }
  return map[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchText.value || undefined,
      status: statusFilter.value || undefined
    }
    const res = await request.get('/sales/quote-estimations/', { params })
    tableData.value = res.data.results || res.data
    total.value = res.data.count || tableData.value.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  const res = await request.get('/masterdata/customers/', { params: { page_size: 1000 } })
  customers.value = res.data.results || res.data
}

const loadOpportunities = async () => {
  const res = await request.get('/sales/opportunities/', { params: { page_size: 1000 } })
  opportunities.value = res.data.results || res.data
}

const handleCreate = () => {
  dialogTitle.value = '新建报价估算'
  Object.assign(form, {
    id: null,
    name: '',
    customer: null,
    opportunity: null,
    project_type: '',
    project_description: '',
    technical_requirements: '',
    management_rate: 10,
    risk_rate: 5,
    target_profit_rate: 20
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑报价估算'
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleView = (row) => {
  router.push(`/sales/quote-estimation/${row.id}`)
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  
  submitting.value = true
  try {
    if (form.id) {
      await request.patch(`/api/sales/quote-estimations/${form.id}/`, form)
      ElMessage.success('保存成功')
    } else {
      const res = await request.post('/sales/quote-estimations/', form)
      ElMessage.success('创建成功')
      router.push(`/sales/quote-estimation/${res.data.id}`)
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const handleCommand = async (cmd, row) => {
  try {
    switch (cmd) {
      case 'calculate':
        await request.post(`/api/sales/quote-estimations/${row.id}/calculate/`)
        ElMessage.success('计算完成')
        loadData()
        break
      case 'submit':
        await ElMessageBox.confirm('确定提交评审?', '提示')
        await request.post(`/api/sales/quote-estimations/${row.id}/submit_review/`)
        ElMessage.success('已提交评审')
        loadData()
        break
      case 'approve':
        await ElMessageBox.confirm('确定审批通过?', '提示')
        await request.post(`/api/sales/quote-estimations/${row.id}/approve/`)
        ElMessage.success('审批通过')
        loadData()
        break
      case 'create_quote':
        await ElMessageBox.confirm('确定生成正式报价单?', '提示')
        const res = await request.post(`/api/sales/quote-estimations/${row.id}/create_quotation/`)
        ElMessage.success(`报价单 ${res.data.quotation_no} 创建成功`)
        loadData()
        break
      case 'import_bom':
        router.push(`/sales/quote-estimation/${row.id}?tab=materials`)
        break
      case 'import_history':
        router.push(`/sales/quote-estimation/${row.id}?tab=reference`)
        break
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('操作失败')
    }
  }
}

onMounted(() => {
  loadData()
  loadCustomers()
  loadOpportunities()
})
</script>

<style scoped>
.filter-card {
  margin-bottom: 16px;
}
.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-right {
  display: flex;
  align-items: center;
}
.money {
  font-weight: 500;
}
.money.primary {
  color: #409eff;
}
</style>
