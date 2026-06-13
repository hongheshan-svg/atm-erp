<template>
  <div class="asset-borrow-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>资产借用</span>
          <el-button type="primary" v-permission="'oa:asset_borrow:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建借用
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 130px;">
            <el-option label="待审批" value="PENDING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="借用中" value="BORROWED" />
            <el-option label="已归还" value="RETURNED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column prop="borrow_no" label="借用单号" width="140" />
        <el-table-column prop="asset_name" label="资产" min-width="150" show-overflow-tooltip />
        <el-table-column prop="borrower_name" label="借用人" width="100" />
        <el-table-column prop="borrow_date" label="借用日期" width="120" />
        <el-table-column prop="expected_return_date" label="预计归还" width="120" />
        <el-table-column prop="actual_return_date" label="实际归还" width="120" />
        <el-table-column prop="purpose" label="借用目的" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING'" size="small" type="primary" @click="handleSubmit(row)">提交</el-button>
            <el-button v-if="row.status === 'PENDING'" size="small" type="success" v-permission="'oa:asset_borrow:edit'" @click="handleApprove(row)">审批通过</el-button>
            <el-button v-if="row.status === 'PENDING'" size="small" type="danger" v-permission="'oa:asset_borrow:edit'" @click="handleReject(row)">拒绝</el-button>
            <el-button v-if="row.status === 'APPROVED'" size="small" type="warning" @click="handleBorrowOut(row)">确认借出</el-button>
            <el-button v-if="row.status === 'BORROWED'" size="small" type="success" @click="handleReturn(row)">归还</el-button>
            <el-button v-if="row.status === 'PENDING'" size="small" type="danger" v-permission="'oa:asset_borrow:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建借用对话框 -->
    <el-dialog v-model="dialogVisible" title="新建资产借用" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="资产" prop="asset">
          <el-select v-model="form.asset" placeholder="选择资产" filterable style="width: 100%">
            <el-option v-for="a in assets" :key="a.id" :label="`${a.asset_no} ${a.name}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="借用人" prop="borrower">
          <el-select v-model="form.borrower" placeholder="选择借用人(默认本人)" filterable clearable style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="借用日期" prop="borrow_date">
          <el-date-picker v-model="form.borrow_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预计归还" prop="expected_return_date">
          <el-date-picker v-model="form.expected_return_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="借用目的" prop="purpose">
          <el-input v-model="form.purpose" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存并提交</el-button>
      </template>
    </el-dialog>

    <!-- 归还对话框 -->
    <el-dialog v-model="returnDialogVisible" title="资产归还" width="500px" destroy-on-close>
      <el-form :model="returnForm" label-width="100px">
        <el-form-item label="归还状况">
          <el-input v-model="returnForm.condition" placeholder="如：完好" />
        </el-form-item>
        <el-form-item label="归还备注">
          <el-input v-model="returnForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="returnDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmReturn">确认归还</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getAssetBorrows, createAssetBorrow, submitAssetBorrow, approveAssetBorrow,
  rejectAssetBorrow, borrowAsset, returnAssetBorrow, deleteAssetBorrow, getAssets
} from '@/api/oa'
import { getUsers } from '@/api/auth'

const loading = ref(false)
const saving = ref(false)
const list = ref<any[]>([])
const assets = ref<any[]>([])
const users = ref<any[]>([])
const dialogVisible = ref(false)
const returnDialogVisible = ref(false)
const currentItem = ref<any>(null)
const formRef = ref()

const searchForm = reactive({ status: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  asset: null,
  borrower: null,
  borrow_date: '',
  expected_return_date: '',
  purpose: ''
})

const returnForm = reactive({ condition: '完好', remarks: '' })

const rules = {
  asset: [{ required: true, message: '请选择资产', trigger: 'change' }],
  expected_return_date: [{ required: true, message: '请选择预计归还日期', trigger: 'change' }],
  purpose: [{ required: true, message: '请输入借用目的', trigger: 'blur' }]
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    BORROWED: 'primary',
    RETURNED: '',
    CANCELLED: 'info'
  }
  return types[status] || 'info'
}

const loadAssets = async () => {
  try {
    const res = await getAssets({ page_size: 1000 })
    assets.value = Array.isArray(res) ? res : (res.results || [])
  } catch (error) {
    console.error('加载资产失败', error)
  }
}

const loadUsers = async () => {
  try {
    const res = await getUsers({ page_size: 1000 })
    const userData = Array.isArray(res) ? res : (res.results || [])
    users.value = userData.map((u: any) => ({
      id: u.id,
      name: u.name || `${u.last_name || ''}${u.first_name || ''}` || u.username,
      username: u.username
    }))
  } catch (error) {
    console.error('加载用户失败', error)
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    const res = await getAssetBorrows(params)
    if (Array.isArray(res)) {
      list.value = res
      pagination.total = res.length
    } else if (res && res.results) {
      list.value = res.results
      pagination.total = res.count || 0
    } else {
      list.value = []
      pagination.total = 0
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  const today = new Date().toISOString().slice(0, 10)
  Object.assign(form, { asset: null, borrower: null, borrow_date: today, expected_return_date: '', purpose: '' })
  if (assets.value.length === 0) loadAssets()
  if (users.value.length === 0) loadUsers()
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    const res = await createAssetBorrow({ ...form })
    const borrowId = res?.id
    if (borrowId) {
      try {
        await submitAssetBorrow(borrowId)
      } catch (e) {
        console.error('submitAssetBorrow error:', e)
      }
    }
    ElMessage.success('已创建并提交')
    dialogVisible.value = false
    loadData()
  } catch (error: any) {
    if (error?.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row: any) => {
  try {
    await submitAssetBorrow(row.id)
    ElMessage.success('提交成功')
    loadData()
  } catch (error) {
    ElMessage.error('提交失败')
  }
}

const handleApprove = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认审批通过该借用申请？', '提示', { type: 'warning' })
    await approveAssetBorrow(row.id)
    ElMessage.success('已审批通过')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleReject = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认拒绝该借用申请？', '提示', { type: 'warning' })
    await rejectAssetBorrow(row.id)
    ElMessage.success('已拒绝')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleBorrowOut = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认借出该资产？资产状态将置为使用中。', '提示', { type: 'warning' })
    await borrowAsset(row.id)
    ElMessage.success('已借出')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleReturn = (row: any) => {
  currentItem.value = row
  Object.assign(returnForm, { condition: '完好', remarks: '' })
  returnDialogVisible.value = true
}

const confirmReturn = async () => {
  saving.value = true
  try {
    await returnAssetBorrow(currentItem.value.id, returnForm)
    ElMessage.success('已归还')
    returnDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm('确定要删除该借用单吗？', '提示', { type: 'warning' })
    await deleteAssetBorrow(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.asset-borrow-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>
