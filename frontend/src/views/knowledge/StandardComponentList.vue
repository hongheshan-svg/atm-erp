<template>
  <div class="component-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>标准部件库</span>
          <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建部件</el-button>
        </div>
      </template>
      
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索部件编码/名称" style="width: 240px" clearable @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchData">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="可用" value="ACTIVE" />
          <el-option label="已废弃" value="DEPRECATED" />
        </el-select>
      </div>

      <el-table :data="components" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column prop="name" label="部件名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="估算成本" width="120" align="right">
          <template #default="{ row }">¥{{ row.estimated_cost?.toLocaleString() || 0 }}</template>
        </el-table-column>
        <el-table-column prop="usage_count" label="使用次数" width="100" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 查看详情 -->
    <el-dialog v-model="viewDialogVisible" title="部件详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="编码">{{ viewDetail.code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ viewDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="分类">{{ viewDetail.category_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ viewDetail.version || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="估算成本">¥{{ viewDetail.estimated_cost?.toLocaleString() || 0 }}</el-descriptions-item>
        <el-descriptions-item label="使用次数">{{ viewDetail.usage_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ viewDetail.created_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ viewDetail.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="规格参数" :span="2">{{ viewDetail.specifications || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新建部件 -->
    <el-dialog v-model="createDialogVisible" title="新建标准部件" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="部件名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="form.code" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="form.version" placeholder="如 V1.0" />
        </el-form-item>
        <el-form-item label="估算成本">
          <el-input-number v-model="form.estimated_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="规格参数">
          <el-input v-model="form.specifications" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { getStandardComponentList, getStandardComponent, createStandardComponent } from '@/api/projects/knowledge'

const loading = ref(false)
const saving = ref(false)
const components = ref([])
const total = ref(0)
const viewDialogVisible = ref(false)
const createDialogVisible = ref(false)
const viewDetail = ref({})
const formRef = ref(null)

const queryParams = reactive({ search: '', status: '', page: 1, page_size: 20 })
const form = reactive({ name: '', code: '', version: '', estimated_cost: 0, description: '', specifications: '' })
const rules = { name: [{ required: true, message: '请输入部件名称', trigger: 'blur' }] }
const getStatusType = (status) => ({ DRAFT: 'info', ACTIVE: 'success', DEPRECATED: 'danger' }[status] || '')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getStandardComponentList(queryParams)
    components.value = res.results || res || []
    total.value = res.count || components.value.length
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  Object.assign(form, { name: '', code: '', version: '', estimated_cost: 0, description: '', specifications: '' })
  formRef.value?.resetFields()
  createDialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getStandardComponent(row.id)
    viewDetail.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    console.error(error)
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    await createStandardComponent(form)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    fetchData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

onMounted(() => fetchData())
</script>

<style scoped>
.component-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-area { display: flex; gap: 12px; flex-wrap: wrap; }
</style>
