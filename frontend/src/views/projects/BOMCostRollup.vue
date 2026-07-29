<template>
  <div class="bom-cost-rollup">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="成本快照数" :value="stats.totalSnapshots" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="平均物料成本" :value="stats.avgMaterialCost" prefix="¥" :precision="2" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="平均人工成本" :value="stats.avgLaborCost" prefix="¥" :precision="2" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="平均总成本" :value="stats.avgTotalCost" prefix="¥" :precision="2" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 项目选择 & 计算 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>BOM成本卷积</span>
              <div>
                <el-button type="primary" @click="showCalculateDialog = true">
                  <el-icon><Cpu /></el-icon>计算成本
                </el-button>
                <el-button @click="showCompareDialog = true">
                  <el-icon><DataLine /></el-icon>成本对比
                </el-button>
              </div>
            </div>
          </template>

          <!-- 批量操作 -->

          <div v-if="selectedRows.length > 0" class="batch-toolbar">

            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

            <el-button size="small" @click="batchExport">导出选中</el-button>

          </div>

          <el-table :data="snapshots" v-loading="loading" stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="project_name" label="项目" min-width="180" />
            <el-table-column prop="version_label" label="版本" width="100" />
            <el-table-column prop="total_material_cost" label="物料成本" width="130" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.total_material_cost) }}</template>
            </el-table-column>
            <el-table-column prop="total_labor_cost" label="人工成本" width="130" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.total_labor_cost) }}</template>
            </el-table-column>
            <el-table-column prop="total_overhead_cost" label="制造费用" width="130" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.total_overhead_cost) }}</template>
            </el-table-column>
            <el-table-column prop="grand_total" label="总成本" width="130" align="right">
              <template #default="{ row }">
                <span style="font-weight:bold;color:#409eff">¥{{ formatMoney(row.grand_total) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="计算时间" width="160" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="viewDetail(row)">明细</el-button>
                <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size"
              :total="total" :page-sizes="[20, 50]" layout="total, prev, pager, next" @change="loadList" />
          </div>
        </el-card>
      </el-col>

      <!-- 成本构成饼图 -->
      <el-col :span="8">
        <el-card>
          <template #header>成本构成分析</template>
          <div ref="pieChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 成本明细抽屉 -->
    <el-drawer v-model="detailVisible" :title="'成本明细 - ' + (selectedSnapshot?.version_label || '')" size="700px">
      <el-table :data="costDetails" stripe size="small">
        <el-table-column prop="material_code" label="物料编码" width="120" />
        <el-table-column prop="material_name" label="物料名称" min-width="160" />
        <el-table-column prop="bom_level" label="BOM层级" width="80" align="center" />
        <el-table-column prop="quantity" label="需求数量" width="100" align="right" />
        <el-table-column prop="unit_material_cost" label="单价" width="100" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.unit_material_cost) }}</template>
        </el-table-column>
        <el-table-column prop="extended_material_cost" label="小计" width="120" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.extended_material_cost) }}</template>
        </el-table-column>
        <el-table-column prop="labor_cost" label="人工" width="100" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.labor_cost) }}</template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 计算对话框 -->
    <el-dialog v-model="showCalculateDialog" title="计算BOM成本" width="500px">
      <el-form label-width="100px">
        <el-form-item label="项目">
          <el-input v-model="calcForm.project_id" placeholder="项目ID" />
        </el-form-item>
        <el-form-item label="版本标签">
          <el-input v-model="calcForm.version_label" placeholder="如: V1.0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCalculateDialog = false">取消</el-button>
        <el-button type="primary" @click="calculateCost" :loading="calcLoading">开始计算</el-button>
      </template>
    </el-dialog>

    <!-- 成本对比对话框 -->
    <el-dialog v-model="showCompareDialog" title="成本版本对比" width="500px">
      <el-form label-width="100px">
        <el-form-item label="快照1">
          <el-select v-model="compareForm.snapshot_id_1" style="width:100%">
            <el-option v-for="s in snapshots" :key="s.id" :label="s.project_name + ' - ' + s.version_label" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="快照2">
          <el-select v-model="compareForm.snapshot_id_2" style="width:100%">
            <el-option v-for="s in snapshots" :key="s.id" :label="s.project_name + ' - ' + s.version_label" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCompareDialog = false">取消</el-button>
        <el-button type="primary" @click="compareCost">对比</el-button>
      </template>
    </el-dialog>

    <!-- 成本对比结果 -->
    <el-dialog v-model="compareResultVisible" title="成本版本对比结果" width="720px">
      <el-table :data="compareRows" stripe size="small">
        <el-table-column prop="label" label="成本项" width="140" />
        <el-table-column label="快照1" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.a) }}</template>
        </el-table-column>
        <el-table-column label="快照2" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.b) }}</template>
        </el-table-column>
        <el-table-column label="差异" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.diff > 0 ? '#f56c6c' : (row.diff < 0 ? '#67c23a' : '') }">
              {{ row.diff > 0 ? '+' : '' }}¥{{ formatMoney(row.diff) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="compareResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cpu, DataLine } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import {
getBOMCostSnapshots, getBOMCostDetails, calculateBOMCost,
  compareBOMCost, deleteBOMCostSnapshot
} from '@/api/projects/enhancement'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/bom-cost-snapshots/', { onSuccess: () => loadList() })


const loading = ref(false)
const calcLoading = ref(false)
const snapshots = ref<any[]>([])
const costDetails = ref<any[]>([])
const total = ref(0)
const detailVisible = ref(false)
const selectedSnapshot = ref<any>(null)
const showCalculateDialog = ref(false)
const showCompareDialog = ref(false)
const pieChartRef = ref<any>(null)

const stats = reactive<Record<string, any>>({ totalSnapshots: 0, avgMaterialCost: 0, avgLaborCost: 0, avgTotalCost: 0 })
const queryParams = reactive<Record<string, any>>({ page: 1, page_size: 20 })
const calcForm = reactive<Record<string, any>>({ project_id: '', version_label: '' })
const compareForm = reactive<Record<string, any>>({ snapshot_id_1: null, snapshot_id_2: null })
const compareResultVisible = ref(false)
const compareResult = ref<any[]>([])

// 把两个快照的成本字段摊成「成本项 / 快照1 / 快照2 / 差异」的行
const COMPARE_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'total_material_cost', label: '材料成本' },
  { key: 'total_labor_cost', label: '人工成本' },
  { key: 'total_overhead_cost', label: '制造费用' },
  { key: 'total_outsource_cost', label: '外协成本' },
  { key: 'grand_total', label: '总计' }
]

const compareRows = computed(() => {
  const [a, b] = compareResult.value
  if (!a || !b) return []
  return COMPARE_FIELDS.map(f => {
    const av = Number(a[f.key] || 0)
    const bv = Number(b[f.key] || 0)
    return { label: f.label, a: av, b: bv, diff: bv - av }
  })
})

const formatMoney = (v: any) => v ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

// 成本构成饼图：原先只声明了容器 ref，从未初始化，图表区域恒为空白
let pieChartInstance: any = null

const renderPieChart = () => {
  if (!pieChartRef.value) return
  if (!pieChartInstance) {
    pieChartInstance = echarts.init(pieChartRef.value)
  }

  const materialCost = snapshots.value.reduce((s, r) => s + Number(r.total_material_cost || 0), 0)
  const laborCost = snapshots.value.reduce((s, r) => s + Number(r.total_labor_cost || 0), 0)
  const grandTotal = snapshots.value.reduce((s, r) => s + Number(r.grand_total || 0), 0)
  // grand_total 可能还含制造费用等，差额归入「其他」，避免饼图与合计对不上
  const otherCost = Math.max(0, grandTotal - materialCost - laborCost)

  pieChartInstance.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${p.name}: ¥${formatMoney(p.value)} (${p.percent}%)`
    },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        data: [
          { name: '材料成本', value: materialCost },
          { name: '人工成本', value: laborCost },
          { name: '其他', value: otherCost }
        ].filter(d => d.value > 0),
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.3)' } }
      }
    ]
  })
}

const loadList = async () => {
  loading.value = true
  try {
    const res = await getBOMCostSnapshots(queryParams)
    snapshots.value = res.results || res.results || []
    total.value = res.count || res.count || 0
    stats.totalSnapshots = total.value
    if (snapshots.value.length) {
      stats.avgMaterialCost = (snapshots.value.reduce((s, r) => s + Number(r.total_material_cost || 0), 0) / snapshots.value.length).toFixed(2)
      stats.avgLaborCost = (snapshots.value.reduce((s, r) => s + Number(r.total_labor_cost || 0), 0) / snapshots.value.length).toFixed(2)
      stats.avgTotalCost = (snapshots.value.reduce((s, r) => s + Number(r.grand_total || 0), 0) / snapshots.value.length).toFixed(2)
    }
    await nextTick()
    renderPieChart()
  } finally { loading.value = false }
}

const viewDetail = async (row: any) => {
  selectedSnapshot.value = row
  try {
    const res = await getBOMCostDetails({ snapshot: row.id })
    costDetails.value = res.results || res.results || []
    detailVisible.value = true
  } catch (error: any) {
    console.error('BOMCostRollup getBOMCostDetails error:', error)
  }
}

const calculateCost = async () => {
  calcLoading.value = true
  try {
    await calculateBOMCost(calcForm)
    ElMessage.success('成本计算完成')
    showCalculateDialog.value = false
    loadList()
  } finally { calcLoading.value = false }
}

const compareCost = async () => {
  if (!compareForm.snapshot_id_1 || !compareForm.snapshot_id_2) {
    ElMessage.warning('请选择两个快照')
    return
  }
  try {
    // 后端 compare 接口收的是 snapshot_ids 数组；原先发 {snapshot_id_1, snapshot_id_2}
    // 会被判定为「至少选择两个快照」直接 400，该功能从未成功过。
    // 返回值也曾被丢弃，用户点「对比」看不到任何差异明细。
    const res = await compareBOMCost({
      snapshot_ids: [compareForm.snapshot_id_1, compareForm.snapshot_id_2]
    })
    compareResult.value = Array.isArray(res) ? res : (res?.results || [])
    showCompareDialog.value = false
    compareResultVisible.value = true
  } catch (error: any) {
    console.error('BOMCostRollup compareBOMCost error:', error)
  }
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm('确认删除？', '提示')
  await deleteBOMCostSnapshot(row.id)
  ElMessage.success('删除成功')
  loadList()
}

const handleResize = () => { pieChartInstance?.resize() }

onMounted(() => {
  loadList()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChartInstance?.dispose()
  pieChartInstance = null
})
</script>

<style scoped>
.bom-cost-rollup { padding: 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
