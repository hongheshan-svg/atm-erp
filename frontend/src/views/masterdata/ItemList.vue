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

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
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
          <el-select v-model="form.unit" placeholder="选择单位">
            <el-option label="个" value="PCS" />
            <el-option label="千克" value="KG" />
            <el-option label="米" value="M" />
            <el-option label="平方米" value="M2" />
            <el-option label="立方米" value="M3" />
            <el-option label="套" value="SET" />
            <el-option label="箱" value="BOX" />
            <el-option label="包" value="PACK" />
            <el-option label="小时" value="HOUR" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准成本">
          <el-input-number v-model="form.standard_cost" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="最小库存">
          <el-input-number v-model="form.min_stock" :min="0" />
        </el-form-item>
        <el-form-item label="最大库存">
          <el-input-number v-model="form.max_stock" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        
        <!-- 附件上传 -->
        <el-form-item label="相关附件">
          <!-- 编辑时使用完整附件组件 -->
          <AttachmentUpload
            v-if="isEdit && form.id"
            ref="attachmentRef"
            related-model="Item"
            :related-id="form.id"
            title="物料附件"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.dwg,.dxf,.jpg,.jpeg,.png,.gif,.zip,.rar"
          />
          <!-- 新增时使用简化的文件选择 -->
          <div v-else class="temp-upload">
            <el-upload
              ref="tempUploadRef"
              :auto-upload="false"
              :file-list="tempFiles"
              :on-change="handleTempFileChange"
              :on-remove="handleTempFileRemove"
              multiple
              accept=".pdf,.doc,.docx,.xls,.xlsx,.dwg,.dxf,.jpg,.jpeg,.png,.gif,.zip,.rar"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon>
                选择附件
              </el-button>
              <template #tip>
                <div class="el-upload__tip">
                  支持图纸(dwg/dxf)、规格书(pdf/doc)、图片等，单个文件不超过50MB
                </div>
              </template>
            </el-upload>
          </div>
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
import { Upload } from '@element-plus/icons-vue'
import request from '@/utils/request'
import AttachmentUpload from '@/components/AttachmentUpload.vue'

const attachmentRef = ref(null)
const tempUploadRef = ref(null)
const tempFiles = ref([])

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
  unit: 'PCS',
  standard_cost: 0,
  min_stock: 0,
  max_stock: 0,
  is_active: true
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
    const response = await request.get('/masterdata/items/', { params })
    items.value = response.results || response || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载物料失败')
  } finally {
    loading.value = false
  }
}

const handleTempFileChange = (file, fileList) => {
  // 检查文件大小
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning(`文件 "${file.name}" 超过50MB限制`)
    fileList.pop()
    return
  }
  tempFiles.value = fileList
}

const handleTempFileRemove = (file, fileList) => {
  tempFiles.value = fileList
}

const uploadTempFiles = async (itemId) => {
  if (!tempFiles.value.length) return
  
  const formData = new FormData()
  formData.append('related_model', 'Item')
  formData.append('related_id', itemId)
  formData.append('category', 'OTHER')
  
  for (const file of tempFiles.value) {
    formData.append('files', file.raw)
  }
  
  try {
    await request.post('/core/attachments/batch_upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  } catch (error) {
    console.error('附件上传失败:', error)
    ElMessage.warning('物料已保存，但部分附件上传失败')
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增物料'
  isEdit.value = false
  tempFiles.value = []
  Object.assign(form, {
    id: null,
    sku: '',
    name: '',
    specification: '',
    unit: 'PCS',
    standard_cost: 0,
    min_stock: 0,
    max_stock: 0,
    is_active: true
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
      const response = await request.post('/masterdata/items/', form)
      // 如果有临时附件，上传附件
      if (tempFiles.value.length && response.id) {
        await uploadTempFiles(response.id)
      }
      ElMessage.success('创建物料成功')
    }
    dialogVisible.value = false
    tempFiles.value = []
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

.temp-upload {
  width: 100%;
}

.temp-upload .el-upload__tip {
  color: #909399;
  font-size: 12px;
  margin-top: 5px;
}
</style>
