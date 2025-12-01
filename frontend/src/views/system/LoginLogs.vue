<template>
  <div class="login-logs">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>登录日志</span>
          <el-button type="primary" @click="fetchStatistics">
            <el-icon><DataAnalysis /></el-icon>
            查看统计
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="用户名">
          <el-input v-model="filters.username" placeholder="搜索用户名" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable>
            <el-option label="成功" value="SUCCESS" />
            <el-option label="失败" value="FAILED" />
            <el-option label="锁定" value="LOCKED" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- Table -->
      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="login_time" label="登录时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.login_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="ip_address" label="IP地址" width="140" />
        <el-table-column prop="device_type" label="设备类型" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="failure_reason" label="失败原因" min-width="200" />
        <el-table-column prop="location" label="登录地点" width="150" />
      </el-table>

      <!-- Pagination -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
        class="pagination"
      />
    </el-card>

    <!-- Statistics Dialog -->
    <el-dialog v-model="showStats" title="登录统计" width="600px">
      <div v-if="statistics" class="stats-container">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-statistic title="总登录次数" :value="statistics.total" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="成功" :value="statistics.success" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="失败" :value="statistics.failed" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="锁定" :value="statistics.locked" />
          </el-col>
        </el-row>
        <el-divider />
        <h4>设备分布</h4>
        <el-table :data="statistics.by_device" size="small">
          <el-table-column prop="device_type" label="设备类型" />
          <el-table-column prop="count" label="次数" />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { getLoginLogs, getLoginStatistics } from '@/api/security'
import { DataAnalysis } from '@element-plus/icons-vue'

const loading = ref(false)
const logs = ref([])
const showStats = ref(false)
const statistics = ref(null)
const dateRange = ref([])

const filters = reactive({
  username: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const getStatusType = (status) => {
  const types = {
    SUCCESS: 'success',
    FAILED: 'danger',
    LOCKED: 'warning'
  }
  return types[status] || 'info'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getLoginLogs(params)
    logs.value = res.results || res
    pagination.total = res.count || logs.value.length
  } finally {
    loading.value = false
  }
}

const fetchStatistics = async () => {
  const res = await getLoginStatistics(7)
  statistics.value = res
  showStats.value = true
}

const resetFilters = () => {
  filters.username = ''
  filters.status = ''
  dateRange.value = []
  fetchData()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-form {
  margin-bottom: 20px;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
.stats-container {
  padding: 10px;
}
</style>
