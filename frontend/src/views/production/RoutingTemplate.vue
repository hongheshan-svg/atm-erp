<template>
  <div class="routing-template">
    <el-card class="filter-card">
      <div class="filter-header">
        <el-button type="primary" v-permission="'production:process:create'" @click="handleCreate">
          <el-icon><Plus /></el-icon> 新建工艺模板
        </el-button>
        <div class="filter-right">
          <el-input v-model="searchText" placeholder="搜索" clearable style="width: 180px" @keyup.enter="loadData">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px; margin-left: 10px" @change="loadData">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已废弃" value="OBSOLETE" />
          </el-select>
        </div>
      </div>
    </el-card>

    <el-card class="data-card">
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="code" label="模板编码" width="140" />
        <el-table-column prop="name" label="模板名称" min-width="200" />
        <el-table-column prop="product_category_name" label="产品类别" width="120" />
        <el-table-column label="版本" width="80" align="center">
          <template #default="{ row }">
            v{{ row.version }}
            <el-tag v-if="row.is_current" type="success" size="small" style="margin-left: 4px">当前</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="工序数" width="80" align="center">
          <template #default="{ row }">{{ row.operation_count }}</template>
        </el-table-column>
        <el-table-column label="标准工时" width="100" align="right">
          <template #default="{ row }">{{ row.total_standard_hours }}h</template>
        </el-table-column>
        <el-table-column label="准备工时" width="100" align="right">
          <template #default="{ row }">{{ row.total_setup_hours }}h</template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button type="primary" link v-permission="'production:process:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-dropdown trigger="click" @command="cmd => handleCommand(cmd, row)">
              <el-button type="primary" link>更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="approve" v-if="row.status === 'DRAFT'">审批</el-dropdown-item>
                  <el-dropdown-item command="new_version">新建版本</el-dropdown-item>
                  <el-dropdown-item command="apply">应用到项目</el-dropdown-item>
                  <el-dropdown-item command="copy">复制</el-dropdown-item>
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
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板编码" prop="code">
              <el-input v-model="form.code" placeholder="请输入编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本">
              <el-input v-model="form.version" disabled />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入模板名称" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="产品类别">
              <el-select v-model="form.product_category" filterable clearable placeholder="选择类别" style="width: 100%">
                <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联物料">
              <el-select v-model="form.item" filterable clearable placeholder="选择物料" style="width: 100%">
                <el-option v-for="i in items" :key="i.id" :label="`${i.code} - ${i.name}`" :value="i.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工艺说明">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请输入工艺说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 应用到项目对话框 -->
    <el-dialog v-model="applyDialogVisible" title="应用工艺到项目" width="500px">
      <el-form :model="applyForm" label-width="80px">
        <el-form-item label="选择项目" required>
          <el-select v-model="applyForm.project_id" filterable placeholder="选择项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleApplyToProject" :loading="submitting">确认应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getItemCategoryTree } from '@/api/core'
import { getItemList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'
import {
getRoutingTemplates, createRoutingTemplate, updateRoutingTemplate,
  approveRoutingTemplate, createRoutingTemplateVersion, applyRoutingTemplateToProject
} from '@/api/production'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/core/')


const router = useRouter()

const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const searchText = ref('')
const statusFilter = ref('')

const dialogVisible = ref(false)
const dialogTitle = ref('新建工艺模板')
const applyDialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const categories = ref<any[]>([])
const items = ref<any[]>([])
const projects = ref<any[]>([])
const currentTemplate = ref(null)

const form = reactive({
  id: null,
  code: '',
  name: '',
  version: '1.0',
  product_category: null,
  item: null,
  description: ''
})

const applyForm = reactive({
  project_id: null
})

const rules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', APPROVED: 'success', OBSOLETE: 'danger' }
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
    const res = await getRoutingTemplates(params)
    tableData.value = res.results || res || []
    total.value = res.count || tableData.value.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadCategories = async () => {
  const res = await getItemCategoryTree({ page_size: 500 })
  categories.value = res.results || res || []
}

const loadItems = async () => {
  const res = await getItemList({ page_size: 1000, item_type: 'PRODUCT' })
  items.value = res.results || res || []
}

const loadProjects = async () => {
  const res = await getProjectList({ page_size: 500, status: 'IN_PROGRESS' })
  projects.value = res.results || res || []
}

const handleCreate = () => {
  dialogTitle.value = '新建工艺模板'
  Object.assign(form, {
    id: null,
    code: '',
    name: '',
    version: '1.0',
    product_category: null,
    item: null,
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑工艺模板'
  Object.assign(form, {
    id: row.id,
    code: row.code,
    name: row.name,
    version: row.version,
    product_category: row.product_category,
    item: row.item,
    description: row.description
  })
  dialogVisible.value = true
}

const handleView = (row) => {
  router.push(`/production/routing-template/${row.id}`)
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  
  submitting.value = true
  try {
    if (form.id) {
      await updateRoutingTemplate(form.id, form)
      ElMessage.success('保存成功')
    } else {
      const res = await createRoutingTemplate(form)
      ElMessage.success('创建成功')
      router.push(`/production/routing-template/${res.id}`)
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
      case 'approve':
        await ElMessageBox.confirm('确定审批通过此工艺模板?', '提示')
        await approveRoutingTemplate(row.id)
        ElMessage.success('审批通过')
        loadData()
        break
      case 'new_version': {
        await ElMessageBox.confirm('确定创建新版本?', '提示')
        const res = await createRoutingTemplateVersion(row.id)
        ElMessage.success('新版本创建成功')
        router.push(`/production/routing-template/${res.id}`)
        }
        break
      case 'apply':
        currentTemplate.value = row
        await loadProjects()
        applyForm.project_id = null
        applyDialogVisible.value = true
        break
      case 'copy': {
        // 复制模板
        const copyData = { ...row, code: `${row.code}_COPY`, id: null }
        await createRoutingTemplate(copyData)
        ElMessage.success('复制成功')
        loadData()
        }
        break
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('操作失败')
    }
  }
}

const handleApplyToProject = async () => {
  if (!applyForm.project_id) {
    ElMessage.warning('请选择项目')
    return
  }
  
  submitting.value = true
  try {
    await applyRoutingTemplateToProject(currentTemplate.value.id, applyForm)
    ElMessage.success('工艺已应用到项目')
    applyDialogVisible.value = false
  } catch (e) {
    console.error(e)
    ElMessage.error('应用失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadData()
  loadCategories()
  loadItems()
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
</style>
