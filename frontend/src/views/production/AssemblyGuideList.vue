<template>
  <div class="assembly-guide-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>装配指导</span>
          <el-button type="primary" @click="handleCreate">新建指导</el-button>
        </div>
      </template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="guide_code" label="编号" width="120" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="product_name" label="产品" width="150" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="steps_count" label="步骤数" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑装配指导' : '新建装配指导'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="产品">
          <el-input v-model="form.product_name" placeholder="关联产品名称" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="form.version" placeholder="如 V1.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, name: '', product_name: '', version: '', description: '' })
const rules = { name: [{ required: true, message: '请输入名称', trigger: 'blur' }] }
const getStatusType = (s) => ({ 'DRAFT': 'info', 'APPROVED': 'success', 'OBSOLETE': 'danger' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/production/assembly-guides/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', product_name: '', version: '', description: '' })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, product_name: row.product_name, version: row.version, description: row.description })
  dialogVisible.value = true
}

const handleView = (row) => router.push({ name: 'AssemblyGuideDetail', params: { id: row.id } })

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await request.put(`/production/assembly-guides/${form.id}/`, form)
      ElMessage.success('更新成功')
    } else {
      await request.post('/production/assembly-guides/', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
