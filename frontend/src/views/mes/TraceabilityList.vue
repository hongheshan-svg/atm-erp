<template>
  <div class="traceability-list">
    <el-card class="header-card">
      <div class="header-content">
        <h2>追溯管理</h2>
        <el-input
          v-model="searchValue"
          placeholder="输入批次号/产品编码/工单号搜索"
          style="width: 400px"
          @keyup.enter="searchTrace"
        >
          <template #prepend>
            <el-select v-model="searchType" style="width: 100px">
              <el-option label="批次号" value="lot" />
              <el-option label="产品" value="item" />
              <el-option label="工单" value="order" />
            </el-select>
          </template>
          <template #append>
            <el-button @click="searchTrace">
              <el-icon><Search /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>
    </el-card>

    <el-row :gutter="16">
      <!-- 批次列表 -->
      <el-col :span="10">
        <el-card>
          <template #header>产品批次</template>
          <el-table :data="lots" v-loading="loading" stripe @row-click="selectLot" highlight-current-row>
            <el-table-column prop="lot_no" label="批次号" width="130" />
            <el-table-column prop="item_name" label="产品" min-width="120" />
            <el-table-column prop="quantity" label="数量" width="80" align="right" />
            <el-table-column prop="production_date" label="生产日期" width="100" />
            <el-table-column prop="inspection_result_display" label="质检" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getInspectionType(row.inspection_result)" size="small">
                  {{ row.inspection_result_display }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            layout="total, prev, pager, next"
            @change="loadLots"
            class="pagination"
          />
        </el-card>
      </el-col>

      <!-- 追溯详情 -->
      <el-col :span="14">
        <el-card v-if="currentLot">
          <template #header>
            <div class="detail-header">
              <span>批次追溯: {{ currentLot.lot_no }}</span>
              <el-tag :type="getInspectionType(currentLot.inspection_result)">
                {{ currentLot.inspection_result }}
              </el-tag>
            </div>
          </template>

          <el-tabs v-model="activeTab">
            <el-tab-pane label="基本信息" name="info">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="批次号">{{ traceData.lot_no }}</el-descriptions-item>
                <el-descriptions-item label="生产日期">{{ traceData.production_date }}</el-descriptions-item>
                <el-descriptions-item label="产品编码">{{ traceData.item?.code }}</el-descriptions-item>
                <el-descriptions-item label="产品名称">{{ traceData.item?.name }}</el-descriptions-item>
                <el-descriptions-item label="数量">{{ traceData.quantity }}</el-descriptions-item>
                <el-descriptions-item label="质检结果">{{ traceData.inspection_result }}</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>

            <el-tab-pane label="物料来源" name="materials">
              <el-table :data="traceData.upstream" border size="small">
                <el-table-column prop="item_code" label="物料编码" width="120" />
                <el-table-column prop="item_name" label="物料名称" />
                <el-table-column prop="batch_no" label="批次" width="120" />
                <el-table-column prop="quantity" label="用量" width="80" align="right" />
                <el-table-column prop="supplier" label="供应商" width="120" />
                <el-table-column prop="purchase_order" label="采购单" width="120" />
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="事件时间线" name="timeline">
              <el-timeline>
                <el-timeline-item
                  v-for="(event, index) in traceData.timeline"
                  :key="index"
                  :timestamp="event.time"
                  :type="getEventColor(event.type)"
                  placement="top"
                >
                  <el-card shadow="never">
                    <div class="timeline-content">
                      <strong>{{ event.type_display }}</strong>
                      <span v-if="event.location"> @ {{ event.location }}</span>
                      <p v-if="event.description">{{ event.description }}</p>
                      <small v-if="event.operator">操作人: {{ event.operator }}</small>
                    </div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </el-tab-pane>

            <el-tab-pane label="质量问题" name="issues">
              <el-table :data="traceData.quality_issues" border size="small">
                <el-table-column prop="issue_no" label="问题编号" width="120" />
                <el-table-column prop="title" label="问题标题" />
                <el-table-column prop="severity" label="严重程度" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag :type="getSeverityType(row.severity)" size="small">{{ row.severity }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="80" />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>
        <el-empty v-else description="请选择一个批次查看追溯信息" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const lots = ref([])
const currentLot = ref(null)
const traceData = ref({})
const activeTab = ref('info')
const searchType = ref('lot')
const searchValue = ref('')

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const loadLots = async () => {
  loading.value = true
  try {
    const res = await request.get('/production/product-lots/', {
      params: { page: pagination.page, page_size: pagination.pageSize }
    })
    lots.value = res.results || res || []
    pagination.total = res.count || (Array.isArray(lots.value) ? lots.value.length : 0)
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const searchTrace = async () => {
  if (!searchValue.value) return
  loading.value = true
  try {
    const res = await request.get('/production/traceability/search/', {
      params: { type: searchType.value, value: searchValue.value }
    })
    lots.value = res.data.results
    pagination.total = res.data.total
    
    if (res.data.results.length === 0) {
      ElMessage.info('未找到匹配的批次')
    }
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const selectLot = async (row) => {
  currentLot.value = row
  try {
    const res = await request.get(`/production/product-lots/${row.id}/trace/`)
    traceData.value = res.data
  } catch (error) {
    console.error(error)
  }
}

const getInspectionType = (result) => {
  const map = { PENDING: 'info', PASSED: 'success', FAILED: 'danger', CONDITIONAL: 'warning' }
  return map[result] || 'info'
}

const getEventColor = (type) => {
  const map = {
    PRODUCTION: 'primary', INSPECTION: 'warning', PACKAGING: 'success',
    STORAGE: 'info', SHIPMENT: 'success', INSTALLATION: 'primary'
  }
  return map[type] || 'info'
}

const getSeverityType = (severity) => {
  const map = { LOW: 'info', MEDIUM: 'warning', HIGH: 'danger', CRITICAL: 'danger' }
  return map[severity] || 'info'
}

onMounted(() => {
  loadLots()
})
</script>

<style scoped>
.traceability-list {
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

.header-content h2 {
  margin: 0;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.timeline-content p {
  margin: 8px 0;
  color: #606266;
}

.timeline-content small {
  color: #909399;
}
</style>
