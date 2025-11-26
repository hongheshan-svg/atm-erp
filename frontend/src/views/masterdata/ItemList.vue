<template>
  <div class="item-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>物料主数据</span>
          <el-button type="primary" @click="handleAdd">新增物料</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料编码">
          <el-input v-model="searchForm.sku" placeholder="搜索物料编码" clearable />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="搜索物料名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadItems">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="items" v-loading="loading" stripe border>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="sku" label="物料编码" />
        <el-table-column prop="name" label="物料名称" />
        <el-table-column prop="specification" label="规格" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="standard_cost" label="标准成本" width="120">
          <template #default="{ row }">
            ¥{{ parseFloat(row.standard_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadItems"
        @current-change="loadItems"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="150px">
        <el-form-item label="物料编码" prop="sku">
          <el-input v-model="form.sku" placeholder="请输入物料编码" />
        </el-form-item>
        <el-form-item label="物料名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入物料名称" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.specification" type="textarea" placeholder="请输入规格描述" />
        </el-form-item>
        <el-form-item label="单位" prop="unit">
          <el-input v-model="form.unit" placeholder="例如: 件, 公斤, 米" />
        </el-form-item>
        <el-form-item label="标准成本">
          <el-input-number v-model="form.standard_cost" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="最小库存">
          <el-input-number v-model="form.min_stock_level" :min="0" />
        </el-form-item>
        <el-form-item label="最大库存">
          <el-input-number v-model="form.max_stock_level" :min="0" />
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
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const items = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增物料')
const isEdit = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  sku: '',
  name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  sku: '',
  name: '',
  specification: '',
  unit: '件',
  standard_cost: 0,
  min_stock_level: 0,
  max_stock_level: 0,
  status: 'active'
})

const rules = {
  sku: [{ required: true, message: '请输入物料编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入物料名称', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }]
}

const loadItems = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const { data } = await request.get('/masterdata/items/', { params })
    items.value = data.results || data
    pagination.total = data.count || data.length
  } catch (error) {
    ElMessage.error('加载物料失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增物料'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    sku: '',
    name: '',
    specification: '',
    unit: '件',
    standard_cost: 0,
    min_stock_level: 0,
    max_stock_level: 0,
    status: 'active'
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑物料'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该物料吗？', '警告', {
      type: 'warning'
    })
    await request.delete(`/masterdata/items/${row.id}/`)
    ElMessage.success('删除物料成功')
    loadItems()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除物料失败')
    }
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (isEdit.value) {
      await request.put(`/masterdata/items/${form.id}/`, form)
      ElMessage.success('更新物料成功')
    } else {
      await request.post('/masterdata/items/', form)
      ElMessage.success('创建物料成功')
    }
    dialogVisible.value = false
    loadItems()
  } catch (error) {
    ElMessage.error('保存物料失败')
  }
}

const resetSearch = () => {
  Object.assign(searchForm, { sku: '', name: '' })
  pagination.page = 1
  loadItems()
}

onMounted(() => {
  loadItems()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>
