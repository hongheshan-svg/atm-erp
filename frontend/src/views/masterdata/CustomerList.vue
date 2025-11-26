<template>
  <div class="customer-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>客户管理</span>
          <el-button type="primary" @click="handleAdd">新增客户</el-button>
        </div>
      </template>

      <el-table :data="customers" v-loading="loading" stripe border>
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="客户名称" />
        <el-table-column prop="contact" label="联系人" />
        <el-table-column prop="phone" label="电话" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="success" @click="handleViewAttachments(row)">附件</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px">
      <el-form :model="form" ref="formRef" label-width="120px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" type="textarea" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`${currentCustomer?.name || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentCustomer"
        related-model="Customer"
        :related-id="currentCustomer.id"
        title="客户相关资料"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import AttachmentUpload from '@/components/AttachmentUpload.vue'

const loading = ref(false)
const customers = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增客户')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentCustomer = ref(null)

const form = reactive({
  id: null,
  code: '',
  name: '',
  contact: '',
  phone: '',
  email: '',
  address: '',
  status: 'active'
})

const loadCustomers = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/masterdata/customers/')
    customers.value = data.results || data
  } catch (error) {
    ElMessage.error('加载客户失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增客户'
  isEdit.value = false
  Object.assign(form, { id: null, code: '', name: '', contact: '', phone: '', email: '', address: '', status: 'active' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑客户'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该客户吗？', '警告', { type: 'warning' })
    await request.delete(`/api/masterdata/customers/${row.id}/`)
    ElMessage.success('删除客户成功')
    loadCustomers()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除客户失败')
  }
}

const handleSubmit = async () => {
  try {
    if (isEdit.value) {
      await request.put(`/masterdata/customers/${form.id}/`, form)
      ElMessage.success('更新客户成功')
    } else {
      await request.post('/masterdata/customers/', form)
      ElMessage.success('创建客户成功')
    }
    dialogVisible.value = false
    loadCustomers()
  } catch (error) {
    ElMessage.error('保存客户失败')
  }
}

const handleViewAttachments = (row) => {
  currentCustomer.value = row
  attachmentDialogVisible.value = true
}

onMounted(() => {
  loadCustomers()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

