<template>
  <div class="blacklist-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>供应商黑名单</span>
          <el-button type="danger" v-permission="'purchase:supplier_blacklist:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon> 添加黑名单
          </el-button>
        </div>
      </template>
      
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索供应商" style="width: 220px" clearable @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchData" style="width: 120px">
          <el-option label="有效" value="ACTIVE" />
          <el-option label="已解除" value="LIFTED" />
        </el-select>
      </div>

      <el-table :data="blacklist" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column label="供应商" min-width="200">
          <template #default="{ row }">
            <span class="supplier-name">{{ row.supplier_detail?.name }}</span>
            <div class="text-muted">{{ row.supplier_detail?.code }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="blacklist_date" label="加入日期" width="120" />
        <el-table-column prop="reason" label="加入原因" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'danger' : 'success'">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lifted_date" label="解除日期" width="120" />
        <el-table-column prop="lifted_reason" label="解除原因" width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status === 'ACTIVE'" 
              size="small" 
              type="success" 
              @click="handleLift(row)"
            >
              解除
            </el-button>
            <el-button size="small" @click="handleView(row)">详情</el-button>
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

    <!-- 添加黑名单对话框 -->
    <el-dialog v-model="dialogVisible" title="添加供应商黑名单" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="供应商" prop="supplier">
          <el-select v-model="form.supplier" placeholder="选择供应商" filterable style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="加入日期" prop="blacklist_date">
          <el-date-picker v-model="form.blacklist_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" rows="4" placeholder="请详细说明加入黑名单的原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="danger" @click="handleSave">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- 解除黑名单对话框 -->
    <el-dialog v-model="liftDialogVisible" title="解除黑名单" width="500px">
      <el-form ref="liftFormRef" :model="liftForm" :rules="liftRules" label-width="100px">
        <el-form-item label="供应商">
          <el-input :value="currentRecord?.supplier_detail?.name" disabled />
        </el-form-item>
        <el-form-item label="解除原因" prop="reason">
          <el-input v-model="liftForm.reason" type="textarea" rows="4" placeholder="请说明解除黑名单的原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="liftDialogVisible = false">取消</el-button>
        <el-button type="success" @click="confirmLift">确认解除</el-button>
      </template>
    </el-dialog>

    <!-- 黑名单详情 -->
    <el-dialog v-model="viewDialogVisible" title="黑名单详情" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="供应商">{{ viewDetail.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="列入日期">{{ viewDetail.blacklist_date }}</el-descriptions-item>
        <el-descriptions-item label="列入原因">{{ viewDetail.reason }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="viewDetail.status === 'ACTIVE' ? 'danger' : 'success'">{{ viewDetail.status === 'ACTIVE' ? '有效' : '已解除' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="viewDetail.lifted_date" label="解除日期">{{ viewDetail.lifted_date }}</el-descriptions-item>
        <el-descriptions-item v-if="viewDetail.lift_reason" label="解除原因">{{ viewDetail.lift_reason }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ viewDetail.created_by_name || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { getBlacklistList, createBlacklist, liftBlacklist } from '@/api/purchase/evaluation'

const loading = ref(false)
const blacklist = ref([])
const total = ref(0)
const suppliers = ref([])
const dialogVisible = ref(false)
const liftDialogVisible = ref(false)
const currentRecord = ref(null)

const queryParams = reactive({
  search: '',
  status: '',
  page: 1,
  page_size: 20
})

const form = reactive({
  supplier: null,
  blacklist_date: new Date().toISOString().split('T')[0],
  reason: ''
})

const liftForm = reactive({
  reason: ''
})

const rules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  blacklist_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  reason: [{ required: true, message: '请输入原因', trigger: 'blur' }]
}

const liftRules = {
  reason: [{ required: true, message: '请输入解除原因', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getBlacklistList(queryParams)
    blacklist.value = res.results || res || []
    total.value = res.count || blacklist.value.length
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  Object.assign(form, {
    supplier: null,
    blacklist_date: new Date().toISOString().split('T')[0],
    reason: ''
  })
  dialogVisible.value = true
}

const viewDialogVisible = ref(false)
const viewDetail = ref({})

const handleView = async (row) => {
  viewDetail.value = row
  viewDialogVisible.value = true
}

const handleLift = (row) => {
  currentRecord.value = row
  liftForm.reason = ''
  liftDialogVisible.value = true
}

const handleSave = async () => {
  try {
    await createBlacklist(form)
    ElMessage.success('添加成功')
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const confirmLift = async () => {
  try {
    await liftBlacklist(currentRecord.value.id, liftForm)
    ElMessage.success('解除成功')
    liftDialogVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error('解除失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.blacklist-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-area {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.supplier-name {
  font-weight: 500;
}
.text-muted {
  font-size: 12px;
  color: #909399;
}
</style>
