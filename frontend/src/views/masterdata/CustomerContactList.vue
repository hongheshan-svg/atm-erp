<template>
  <div class="customer-contact-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>客户联系人管理</span>
          <el-button type="primary" v-permission="'masterdata:customer:create'" @click="handleAdd">
            <el-icon><Plus /></el-icon> 新增联系人
          </el-button>
        </div>
      </template>

      <!-- 搜索条件 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="客户">
          <el-select v-model="searchForm.customer" placeholder="选择客户" clearable filterable style="width: 200px;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名/电话">
          <el-input v-model="searchForm.search" placeholder="搜索姓名/电话/邮箱" clearable style="width: 180px;" @keyup.enter="loadContacts" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="searchForm.role" placeholder="全部" clearable style="width: 120px;">
            <el-option label="决策者" value="DECISION_MAKER" />
            <el-option label="影响者" value="INFLUENCER" />
            <el-option label="执行者" value="EXECUTOR" />
            <el-option label="使用者" value="USER" />
            <el-option label="财务" value="FINANCE" />
            <el-option label="技术" value="TECHNICAL" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadContacts">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="contacts" v-loading="loading" stripe border>
        <el-table-column prop="customer_name" label="客户" min-width="180" show-overflow-tooltip />
        <el-table-column prop="name" label="联系人" width="100" />
        <el-table-column prop="title" label="职位" width="120" />
        <el-table-column prop="role_display" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)" size="small">{{ row.role_display || row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="mobile" label="手机" width="130" />
        <el-table-column prop="phone" label="座机" width="130" />
        <el-table-column prop="email" label="邮箱" width="180" show-overflow-tooltip />
        <el-table-column prop="wechat" label="微信" width="120" />
        <el-table-column prop="is_primary" label="主联系人" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_primary" type="success" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="birthday" label="生日" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" v-permission="'masterdata:customer:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" link type="success" @click="handleFollowUp(row)">跟进</el-button>
            <el-button size="small" link type="danger" v-permission="'masterdata:customer:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadContacts"
        @current-change="loadContacts"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px">
      <el-form :model="form" ref="formRef" label-width="100px" :rules="formRules">
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="所属客户" prop="customer">
              <el-select v-model="form.customer" placeholder="选择客户" filterable style="width: 100%;">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人姓名" prop="name">
              <el-input v-model="form.name" placeholder="请输入姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职位">
              <el-input v-model="form.title" placeholder="如：总经理、采购经理" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="角色" prop="role">
              <el-select v-model="form.role" placeholder="选择角色" style="width: 100%;">
                <el-option label="决策者" value="DECISION" />
                <el-option label="技术负责人" value="TECHNICAL" />
                <el-option label="采购负责人" value="PURCHASE" />
                <el-option label="财务负责人" value="FINANCE" />
                <el-option label="项目负责人" value="PROJECT" />
                <el-option label="操作人员" value="OPERATOR" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="主联系人">
              <el-switch v-model="form.is_primary" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="手机号码" prop="mobile">
              <el-input v-model="form.mobile" placeholder="手机号码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="座机">
              <el-input v-model="form.phone" placeholder="座机号码" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" placeholder="电子邮箱" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="微信">
              <el-input v-model="form.wechat" placeholder="微信号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="生日">
              <el-date-picker v-model="form.birthday" type="date" placeholder="选择生日" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门">
              <el-input v-model="form.department" placeholder="所属部门" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="兴趣爱好">
          <el-input v-model="form.hobbies" placeholder="兴趣爱好，用于关系维护" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getCustomerList, getCustomerContactList, createCustomerContact, updateCustomerContact, deleteCustomerContact } from '@/api/masterdata'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const contacts = ref([])
const customers = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增联系人')
const formRef = ref(null)
const isEdit = ref(false)

const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const searchForm = reactive({ customer: null, search: '', role: null })

const form = reactive({
  id: null,
  customer: null,
  name: '',
  title: '',
  department: '',
  role: 'OTHER',
  mobile: '',
  phone: '',
  email: '',
  wechat: '',
  birthday: null,
  hobbies: '',
  notes: '',
  is_primary: false
})

const formRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  name: [{ required: true, message: '请输入联系人姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  mobile: [{ pattern: /^1\d{10}$/, message: '请输入正确的手机号', trigger: 'blur' }]
}

const getRoleType = (role) => {
  const types = {
    DECISION: 'danger',
    TECHNICAL: 'primary',
    PURCHASE: 'warning',
    FINANCE: 'info',
    PROJECT: 'success',
    OPERATOR: '',
    OTHER: 'info'
  }
  return types[role] || 'info'
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 1000, status: 'ACTIVE' })
    customers.value = res.results || res || []
  } catch (error) {
    console.error('Load customers failed:', error)
  }
}

const loadContacts = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    const res = await getCustomerContactList(params)
    contacts.value = res.results || res || []
    pagination.total = res.count || 0
  } catch (error) {
    ElMessage.error('加载联系人失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.search = ''
  searchForm.role = null
  pagination.page = 1
  loadContacts()
}

const handleAdd = () => {
  dialogTitle.value = '新增联系人'
  isEdit.value = false
  Object.assign(form, {
    id: null, customer: searchForm.customer, name: '', title: '', department: '', role: 'OTHER',
    mobile: '', phone: '', email: '', wechat: '', birthday: null,
    hobbies: '', notes: '', is_primary: false
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑联系人'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除联系人 ${row.name} 吗？`, '删除确认', { type: 'warning' })
    await deleteCustomerContact(row.id)
    ElMessage.success('删除成功')
    loadContacts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleFollowUp = (row) => {
  router.push({ path: '/masterdata/customer-followups', query: { customer: row.customer, contact: row.id } })
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    if (isEdit.value) {
      await updateCustomerContact(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createCustomerContact(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadContacts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存失败: ' + (error.response?.data?.error || error.message))
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadCustomers()
  loadContacts()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-form {
  margin-bottom: 15px;
}
</style>
