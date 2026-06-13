<template>
  <div class="aps-scheduling">
    <el-card class="header-card">
      <div class="header-content">
        <div class="title-section">
          <h2>APS高级排程</h2>
          <span class="subtitle">生产计划智能排程优化</span>
        </div>
        <div class="header-actions">
          <el-button @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button type="success" @click="openCreateDialog">
            <el-icon><Plus /></el-icon> 新建工单
          </el-button>
          <el-button type="primary" @click="autoSchedule" :loading="scheduling">
            <el-icon><Magic /></el-icon> 自动排程
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <!-- 产能视图 -->
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>工作中心产能视图</span>
              <el-date-picker
                v-model="capacityStartDate"
                type="date"
                placeholder="开始日期"
                style="width: 150px"
                @change="loadCapacity"
              />
            </div>
          </template>
          <div class="capacity-view" v-loading="loadingCapacity">
            <div v-for="wc in capacityData" :key="wc.work_center_id" class="work-center-row">
              <div class="wc-name">{{ wc.work_center_name }}</div>
              <div class="wc-days">
                <div v-for="day in wc.days" :key="day.date" class="day-capacity">
                  <div class="day-header">{{ formatWeekday(day.date) }}</div>
                  <div class="day-date">{{ formatShortDate(day.date) }}</div>
                  <el-progress 
                    :percentage="day.utilization" 
                    :color="getCapacityColor(day.utilization)"
                    :stroke-width="10"
                  />
                  <div class="capacity-text">
                    {{ day.scheduled.toFixed(1) }}/{{ wc.daily_capacity }}h
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 排程工单列表 -->
    <el-card class="orders-card">
      <template #header>
        <div class="card-header">
          <span>排程工单</span>
          <el-radio-group v-model="orderFilter" size="small" @change="loadOrders">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="PENDING">待排程</el-radio-button>
            <el-radio-button value="SCHEDULED">已排程</el-radio-button>
            <el-radio-button value="IN_PROGRESS">生产中</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="orders" v-loading="loadingOrders" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="order_no" label="工单号" width="140">
          <template #default="{ row }">
            <el-link type="primary">{{ row.order_no }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="item_name" label="产品" width="200" />
        <el-table-column prop="quantity" label="数量" width="100" align="right" />
        <el-table-column prop="required_date" label="需求日期" width="110" />
        <el-table-column prop="work_center_name" label="工作中心" width="120" />
        <el-table-column prop="planned_start" label="计划开始" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.planned_start) }}
          </template>
        </el-table-column>
        <el-table-column prop="planned_end" label="计划结束" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.planned_end) }}
          </template>
        </el-table-column>
        <el-table-column prop="priority_display" label="优先级" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">
              {{ row.priority_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="startOrder(row)" v-if="row.status === 'SCHEDULED'">开始</el-button>
            <el-button link type="success" size="small" @click="completeOrder(row)" v-if="row.status === 'IN_PROGRESS'">完成</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @change="loadOrders"
        class="pagination"
      />
    </el-card>

    <!-- 甘特图视图 -->
    <el-card class="gantt-card">
      <template #header>
        <div class="card-header">
          <span>排程甘特图</span>
          <el-date-picker
            v-model="ganttDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
            @change="loadGantt"
          />
        </div>
      </template>
      <div class="gantt-container" v-loading="loadingGantt">
        <div v-if="ganttData.length === 0" class="no-data">
          暂无排程数据
        </div>
        <div v-else class="gantt-chart">
          <div v-for="item in ganttData" :key="item.id" class="gantt-row">
            <div class="gantt-label">{{ item.order_no }}</div>
            <div class="gantt-bar-container">
              <div 
                class="gantt-bar"
                :style="getGanttBarStyle(item)"
                :class="{ 'completed': item.status === 'COMPLETED' }"
              >
                <span class="bar-text">{{ item.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新建排程工单对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建排程工单" width="560px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="100px">
        <el-form-item label="产品" prop="item">
          <el-select
            v-model="createForm.item"
            filterable
            clearable
            placeholder="请选择产品（可选）"
            style="width: 100%"
          >
            <el-option
              v-for="it in itemOptions"
              :key="it.id"
              :label="`${it.code} ${it.name}`"
              :value="it.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="createForm.quantity" :min="0.0001" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="需求日期" prop="required_date">
          <el-date-picker
            v-model="createForm.required_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择需求日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="createForm.priority" style="width: 100%">
            <el-option label="最高" :value="1" />
            <el-option label="高" :value="2" />
            <el-option label="中" :value="3" />
            <el-option label="低" :value="4" />
            <el-option label="最低" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="工作中心" prop="work_center">
          <el-select
            v-model="createForm.work_center"
            filterable
            clearable
            placeholder="可选，留空由自动排程分配"
            style="width: 100%"
          >
            <el-option
              v-for="wc in workCenterOptions"
              :key="wc.id"
              :label="wc.name"
              :value="wc.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="createForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { getScheduleCapacity, getScheduleOrderList, getScheduleGanttList, autoSchedule as apiAutoSchedule, startScheduleOrder, completeScheduleOrder, createScheduleOrder } from '@/api/mes'
import { getItemList } from '@/api/masterdata'
import { getWorkCenters } from '@/api/production'

// 自定义Magic图标
const Magic = {
  name: 'Magic',
  render() {
    return h('svg', { viewBox: '0 0 1024 1024', width: '1em', height: '1em' }, [
      h('path', { fill: 'currentColor', d: 'M512 64L384 256H128v256l-64 128 64 128v256h256l128 192 128-192h256v-256l64-128-64-128V256H640L512 64zm0 192l64 128h128v128l64 64-64 64v128H576l-64 128-64-128H320V640l-64-64 64-64V384h128l64-128z' })
    ])
  }
}
import { h } from 'vue'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/production/schedule-orders/', { onSuccess: () => loadOrders() })


const loadingCapacity = ref(false)
const loadingOrders = ref(false)
const loadingGantt = ref(false)
const scheduling = ref(false)

const capacityStartDate = ref(new Date())
const capacityData = ref<any[]>([])
const orders = ref<any[]>([])
const ganttData = ref<any[]>([])
const ganttDateRange = ref<any[]>([])
const orderFilter = ref('')

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 新建工单
const createDialogVisible = ref(false)
const creating = ref(false)
const createFormRef = ref()
const itemOptions = ref<any[]>([])
const workCenterOptions = ref<any[]>([])
const createForm = reactive<Record<string, any>>({
  item: null,
  quantity: 1,
  required_date: '',
  priority: 3,
  work_center: null,
  remarks: ''
})
const createRules = {
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  required_date: [{ required: true, message: '请选择需求日期', trigger: 'change' }]
}

const loadCreateOptions = async () => {
  try {
    const [itemsRes, wcRes] = await Promise.all([
      getItemList({ page_size: 200 }),
      getWorkCenters({ is_active: true, page_size: 200 })
    ])
    itemOptions.value = itemsRes.results || itemsRes || []
    workCenterOptions.value = wcRes.results || wcRes || []
  } catch (error) {
    console.error(error)
  }
}

const openCreateDialog = () => {
  createForm.item = null
  createForm.quantity = 1
  createForm.required_date = ''
  createForm.priority = 3
  createForm.work_center = null
  createForm.remarks = ''
  createDialogVisible.value = true
  if (itemOptions.value.length === 0 || workCenterOptions.value.length === 0) {
    loadCreateOptions()
  }
}

const submitCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    creating.value = true
    try {
      await createScheduleOrder({ ...createForm, status: 'PENDING' })
      ElMessage.success('工单已创建')
      createDialogVisible.value = false
      loadOrders()
    } catch (error) {
      console.error(error)
    } finally {
      creating.value = false
    }
  })
}

const loadData = () => {
  loadCapacity()
  loadOrders()
  loadGantt()
}

const loadCapacity = async () => {
  loadingCapacity.value = true
  try {
    const startDate = capacityStartDate.value?.toISOString().split('T')[0]
    const res = await getScheduleCapacity({ start_date: startDate, days: 7 })
    capacityData.value = res || []
  } catch (error) {
    console.error(error)
    capacityData.value = []
  } finally {
    loadingCapacity.value = false
  }
}

const loadOrders = async () => {
  loadingOrders.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (orderFilter.value) {
      params.status = orderFilter.value
    }
    const res = await getScheduleOrderList(params)
    orders.value = res.results || res || []
    pagination.total = res.count || (Array.isArray(orders.value) ? orders.value.length : 0)
  } catch (error) {
    console.error(error)
  } finally {
    loadingOrders.value = false
  }
}

const loadGantt = async () => {
  loadingGantt.value = true
  try {
    const params = {}
    if (ganttDateRange.value?.length === 2) {
      params.start_date = ganttDateRange.value[0].toISOString().split('T')[0]
      params.end_date = ganttDateRange.value[1].toISOString().split('T')[0]
    }
    const res = await getScheduleGanttList(params)
    ganttData.value = res || []
  } catch (error) {
    console.error(error)
    ganttData.value = []
  } finally {
    loadingGantt.value = false
  }
}

const autoSchedule = async () => {
  await ElMessageBox.confirm('确定执行自动排程？这将对待排程工单进行智能调度。', '确认排程')
  scheduling.value = true
  try {
    const res = await apiAutoSchedule()
    ElMessage.success(`排程完成，共处理 ${res.scheduled_count || 0} 个工单`)
    loadData()
  } catch (error) {
    console.error(error)
  } finally {
    scheduling.value = false
  }
}

const startOrder = async (row) => {
  await ElMessageBox.confirm(`确定开始生产工单 ${row.order_no}？`, '确认')
  try {
    await startScheduleOrder(row.id)
    ElMessage.success('已开始生产')
    loadOrders()
  } catch (error) {
    console.error(error)
  }
}

const completeOrder = async (row) => {
  await ElMessageBox.confirm(`确定完成工单 ${row.order_no}？`, '确认')
  try {
    await completeScheduleOrder(row.id, {
      completed_qty: row.quantity
    })
    ElMessage.success('工单已完成')
    loadOrders()
  } catch (error) {
    console.error(error)
  }
}

const getCapacityColor = (utilization) => {
  if (utilization >= 90) return '#F56C6C'
  if (utilization >= 70) return '#E6A23C'
  return '#67C23A'
}

const getPriorityType = (priority) => {
  const map = { 1: 'danger', 2: 'warning', 3: '', 4: 'info', 5: 'info' }
  return map[priority] || 'info'
}

const getStatusType = (status) => {
  const map = { PENDING: 'info', SCHEDULED: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'info' }
  return map[status] || 'info'
}

const getGanttBarStyle = (item) => {
  if (!item.start || !item.end) return {}
  
  const start = new Date(item.start)
  const end = new Date(item.end)
  const rangeStart = ganttDateRange.value?.[0] || new Date()
  const rangeEnd = ganttDateRange.value?.[1] || new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
  
  const totalRange = rangeEnd - rangeStart
  const left = Math.max(0, (start - rangeStart) / totalRange * 100)
  const width = Math.min(100 - left, (end - start) / totalRange * 100)
  
  return {
    left: `${left}%`,
    width: `${Math.max(2, width)}%`
  }
}

const formatWeekday = (dateStr) => {
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return days[new Date(dateStr).getDay()]
}

const formatShortDate = (dateStr) => {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  // 设置默认日期范围
  const today = new Date()
  const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)
  ganttDateRange.value = [today, nextWeek]
  
  loadData()
})
</script>

<style scoped>
.aps-scheduling {
  padding: 0;
}

.header-card {
  margin-bottom: 16px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section h2 {
  margin: 0;
  font-size: 20px;
}

.subtitle {
  color: #909399;
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.capacity-view {
  overflow-x: auto;
}

.work-center-row {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.work-center-row:last-child {
  border-bottom: none;
}

.wc-name {
  width: 120px;
  font-weight: 500;
  flex-shrink: 0;
}

.wc-days {
  display: flex;
  gap: 12px;
  flex: 1;
}

.day-capacity {
  flex: 1;
  min-width: 80px;
  text-align: center;
}

.day-header {
  font-size: 12px;
  color: #909399;
}

.day-date {
  font-weight: 500;
  margin-bottom: 8px;
}

.capacity-text {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}

.orders-card, .gantt-card {
  margin-top: 16px;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.gantt-container {
  min-height: 200px;
}

.no-data {
  text-align: center;
  color: #909399;
  padding: 60px 0;
}

.gantt-row {
  display: flex;
  align-items: center;
  height: 36px;
  border-bottom: 1px solid #ebeef5;
}

.gantt-label {
  width: 120px;
  font-size: 12px;
  padding-right: 12px;
  flex-shrink: 0;
}

.gantt-bar-container {
  flex: 1;
  position: relative;
  height: 24px;
  background: #f5f7fa;
  border-radius: 4px;
}

.gantt-bar {
  position: absolute;
  height: 100%;
  background: linear-gradient(90deg, #409EFF, #66b1ff);
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  overflow: hidden;
}

.gantt-bar.completed {
  background: linear-gradient(90deg, #67C23A, #95d475);
}

.bar-text {
  font-size: 11px;
  color: #fff;
  white-space: nowrap;
}
</style>
