<template>
  <div class="supplier-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>供应商管理</span>
          <el-button type="primary" @click="handleAdd">新增供应商</el-button>
        </div>
      </template>

      <el-table :data="suppliers" v-loading="loading" stripe border>
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="供应商名称" min-width="180" />
        <el-table-column prop="contact_person" label="联系人" width="100" />
        <el-table-column prop="phone" label="电话" width="130" />
        <el-table-column prop="email" label="邮箱" width="180" />
        <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">{{ row.status === 'ACTIVE' ? '激活' : '停用' }}</el-tag>
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
        <el-form-item label="编码">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_person" />
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
            <el-option label="激活" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`${currentSupplier?.name || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentSupplier"
        related-model="Supplier"
        :related-id="currentSupplier.id"
        title="供应商相关资料"
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
const suppliers = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增供应商')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentSupplier = ref(null)

const form = reactive({
  id: null,
  code: '',
  name: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  status: 'ACTIVE'
})

const loadSuppliers = async () => {
  loading.value = true
  try {
    const response = await request.get('/masterdata/suppliers/')
    suppliers.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载供应商失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增供应商'
  isEdit.value = false
  Object.assign(form, { id: null, code: '', name: '', contact_person: '', phone: '', email: '', address: '', status: 'ACTIVE' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑供应商'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该供应商吗？', '警告', { type: 'warning' })
    await request.delete(`/masterdata/suppliers/${row.id}/`)
    ElMessage.success('删除供应商成功')
    loadSuppliers()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除供应商失败')
  }
}

const handleSubmit = async () => {
  try {
    if (isEdit.value) {
      await request.put(`/masterdata/suppliers/${form.id}/`, form)
      ElMessage.success('更新供应商成功')
    } else {
      await request.post('/masterdata/suppliers/', form)
      ElMessage.success('创建供应商成功')
    }
    dialogVisible.value = false
    loadSuppliers()
  } catch (error) {
    ElMessage.error('保存供应商失败')
  }
}

const handleViewAttachments = (row) => {
  currentSupplier.value = row
  attachmentDialogVisible.value = true
}

onMounted(() => {
  loadSuppliers()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

